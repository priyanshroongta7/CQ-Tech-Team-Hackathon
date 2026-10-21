"""
CQ Tech Team AI Agent — Master Pipeline (LangGraph Orchestrator)

Strictly matches the Problem Statement requirements:
1. Inputs: Accepts a search prompt OR an uploaded event brochure (PDF).
2. Targets: Finds both Sponsors (companies) and College Delegations (college societies).
3. Where it looks: Company websites, team pages, LinkedIn, social pages, college society sites.
4. Output Schema (6 Mandatory Fields):
   - Organization Name: Company or society name.
   - Category: Sponsor or College Delegation.
   - Location: City.
   - Contact Person: Name and role of the decision-maker.
   - Contact Channel: A real email address or an authentic profile link.
   - Verification Status: Verified or Pattern-Derived.
5. LangGraph StateGraph Architecture:
   - 5 Nodes (parse_input, research_lead, verify_lead, push_to_sheets, advance_queue)
   - Conditional routing to drop failed/fake contacts and loop until queue is complete.
"""

import sys
import time
from typing import TypedDict, Literal

from langgraph.graph import StateGraph, END

from phase1_context import extract_input_content, generate_master_list
from phase2_orchestration import run_research, parse_research_result
from phase3_verification import process_contact
from phase4_output import authenticate_google_sheets, push_lead_to_sheet

# ─── Configuration ────────────────────────────────────────────────────────────
DEFAULT_INPUT = sys.argv[1] if len(sys.argv) > 1 else "brochure.pdf"
CREDENTIALS_FILE = "credentials.json"
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1npEIdK2L0DXVqhzjLbucwzgpMJBK_6HQKxiLDe0dmI8/edit?gid=0#gid=0"


# ─── LangGraph State Schema ──────────────────────────────────────────────────
class AgentState(TypedDict):
    """Typed state that flows through every node in the graph."""
    raw_input: str
    target_leads_queue: list[dict]  # List of {name, category, query, role}
    current_index: int
    current_item: dict

    # Phase 2 outputs
    researched_person: str
    researched_role: str
    researched_city: str
    researched_profile: str

    # Phase 3 output
    contact_data: dict

    # Accumulator
    results: list[dict]
    google_client: object


# ─── Graph Nodes ─────────────────────────────────────────────────────────────

def parse_input(state: AgentState) -> dict:
    """NODE 1 — Phase 1: Parse brochure PDF or search prompt to generate target leads."""
    print("\n" + "=" * 60)
    print("  LANGGRAPH NODE ▸ parse_input  (Phase 1 Context Generation)")
    print("=" * 60)

    input_text = extract_input_content(state["raw_input"])
    master_list = generate_master_list(input_text)

    # Flatten into a task queue: (organization, category, query, role)
    queue = []
    if master_list.target_leads:
        for lead in master_list.target_leads:
            roles = lead.target_roles or ["Decision Maker"]
            for role in roles:
                queue.append({
                    "organization_name": lead.name,
                    "category": lead.category,
                    "query": lead.domain_or_query,
                    "target_role": role
                })
    else:
        # Backward compatibility if target_leads is empty
        domains = master_list.target_domains or ["Tech Mahindra"]
        roles = master_list.job_titles or ["Marketing Lead"]
        for domain in domains:
            for role in roles:
                queue.append({
                    "organization_name": domain,
                    "category": "Sponsor",
                    "query": domain,
                    "target_role": role
                })

    print(f"  Total targets generated in search queue: {len(queue)}")
    for i, item in enumerate(queue, 1):
        print(f"    {i}. [{item['category']}] {item['organization_name']} -> Role: {item['target_role']}")

    google_client = None
    try:
        google_client = authenticate_google_sheets(CREDENTIALS_FILE)
    except Exception as e:
        print(f"  Note: Google Sheets client deferred ({e}). Will push when credentials are provided.")

    first_item = queue[0] if queue else {}

    return {
        "raw_input": input_text,
        "target_leads_queue": queue,
        "current_index": 0,
        "current_item": first_item,
        "results": [],
        "google_client": google_client,
    }


def research_lead(state: AgentState) -> dict:
    """NODE 2 — Phase 2: CrewAI agent autonomously queries web, LinkedIn, team pages."""
    item = state["current_item"]
    org_name = item.get("organization_name", "Target Organization")
    query = item.get("query", org_name)
    role = item.get("target_role", "Decision Maker")
    category = item.get("category", "Sponsor")

    print("\n" + "-" * 60)
    print(f"  LANGGRAPH NODE ▸ research_lead  (Phase 2 Autonomous Research)")
    print(f"  Target: [{category}] {role} @ {org_name} ({query})")
    print("-" * 60)

    raw_result = run_research(query, role, category=category)
    parsed = parse_research_result(raw_result, default_role=role)
    print(f"  Researched Info -> Name: {parsed['name']} | Role: {parsed['role']} | City: {parsed['city']}")

    return {
        "researched_person": parsed["name"],
        "researched_role": parsed["role"],
        "researched_city": parsed["city"],
        "researched_profile": parsed["profile"],
    }


def verify_lead(state: AgentState) -> dict:
    """NODE 3 — Phase 3: Deliverability verification via Hunter.io / ZeroBounce / Authentic Profile."""
    person_name = state["researched_person"]
    org_name = state["current_item"].get("query", state["current_item"].get("organization_name", ""))
    profile_url = state.get("researched_profile")

    print("\n" + "-" * 60)
    print(f"  LANGGRAPH NODE ▸ verify_lead  (Phase 3 Contact Verification)")
    print(f"  Contact: {person_name} @ {org_name}")
    print("-" * 60)

    contact_data = process_contact(person_name, org_name, profile_url=profile_url)
    return {"contact_data": contact_data}


def push_to_sheets(state: AgentState) -> dict:
    """NODE 4 — Phase 4: Enforces 6-field schema and pushes verified row to Google Sheet."""
    print("\n" + "-" * 60)
    print(f"  LANGGRAPH NODE ▸ push_to_sheets  (Phase 4 Schema & Output)")
    print("-" * 60)

    item = state["current_item"]
    contact = state["contact_data"]
    person_name = contact.get("Name", state["researched_person"])
    role = state.get("researched_role", item.get("target_role", "Decision Maker"))

    # Strictly adheres to the 6-field schema specified in the problem statement
    final_lead = {
        "organization_name": item.get("organization_name", "Organization"),
        "category": item.get("category", "Sponsor"),
        "location": state.get("researched_city", "Bangalore"),
        "contact_person": f"{person_name} - {role}",
        "contact_channel": contact.get("Email", ""),
        "verification_status": contact.get("Verification Status", "Pattern-Derived"),
    }

    print(f"  Pydantic Lead Payload: {final_lead}")

    if state.get("google_client"):
        push_lead_to_sheet(state["google_client"], GOOGLE_SHEET_URL, final_lead)
    else:
        print("  [Local Run] Lead saved to local state results (Google Client not configured).")

    updated_results = state["results"] + [final_lead]
    return {"results": updated_results}


def advance_queue(state: AgentState) -> dict:
    """NODE 5 — Advances to the next item in the queue with rate-limit protection."""
    print("\n" + "-" * 60)
    print(f"  LANGGRAPH NODE ▸ advance_queue")
    print("-" * 60)

    idx = state["current_index"] + 1
    queue = state["target_leads_queue"]

    # Rate limiting delay
    time.sleep(3)

    if idx < len(queue):
        next_item = queue[idx]
        print(f"  → Advancing to task {idx + 1}/{len(queue)}: [{next_item['category']}] {next_item['target_role']} @ {next_item['organization_name']}")
        return {
            "current_index": idx,
            "current_item": next_item
        }
    else:
        print("  → All lead tasks in queue have been processed.")
        return {"current_index": idx}


# ─── Conditional Edge Functions ──────────────────────────────────────────────

def route_after_research(state: AgentState) -> Literal["verify_lead", "advance_queue"]:
    """If person is Not Found, skip verification and advance queue immediately."""
    person = state.get("researched_person", "")
    if "not found" in person.lower() or not person:
        print("  ⤷ Routing decision: Contact NOT FOUND → skipping to next target")
        return "advance_queue"
    print("  ⤷ Routing decision: Contact found → proceeding to verification node")
    return "verify_lead"


def route_after_verification(state: AgentState) -> Literal["push_to_sheets", "advance_queue"]:
    """If verification fails (fake/dead link), drop the lead to avoid hallucination."""
    status = state["contact_data"].get("status", "")
    ver_status = state["contact_data"].get("Verification Status", "")
    if status == "Failed" or not ver_status:
        print("  ⤷ Routing decision: Verification FAILED → dropping dead link / unverified data")
        return "advance_queue"
    print(f"  ⤷ Routing decision: Status = {ver_status} → pushing to Google Sheet")
    return "push_to_sheets"


def route_after_advance(state: AgentState) -> Literal["research_lead", "__end__"]:
    """If more items in queue remain, loop back to research; otherwise finish."""
    if state["current_index"] < len(state["target_leads_queue"]):
        return "research_lead"
    return "__end__"


# ─── Build & Compile the LangGraph ───────────────────────────────────────────

def build_graph():
    """Constructs the LangGraph StateGraph connecting all 5 nodes and decision edges."""
    workflow = StateGraph(AgentState)

    workflow.add_node("parse_input", parse_input)
    workflow.add_node("research_lead", research_lead)
    workflow.add_node("verify_lead", verify_lead)
    workflow.add_node("push_to_sheets", push_to_sheets)
    workflow.add_node("advance_queue", advance_queue)

    workflow.set_entry_point("parse_input")

    workflow.add_edge("parse_input", "research_lead")
    workflow.add_edge("push_to_sheets", "advance_queue")

    workflow.add_conditional_edges(
        "research_lead",
        route_after_research,
        {
            "verify_lead": "verify_lead",
            "advance_queue": "advance_queue",
        },
    )

    workflow.add_conditional_edges(
        "verify_lead",
        route_after_verification,
        {
            "push_to_sheets": "push_to_sheets",
            "advance_queue": "advance_queue",
        },
    )

    workflow.add_conditional_edges(
        "advance_queue",
        route_after_advance,
        {
            "research_lead": "research_lead",
            "__end__": END,
        },
    )

    return workflow.compile()


# ─── Main Execution ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     CQ Tech Team AI Agent — LangGraph Autonomous Orchestrator    ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    input_target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    print(f"Starting pipeline with input target: '{input_target}'\n")

    graph = build_graph()

    final_state = graph.invoke({
        "raw_input": input_target,
        "target_leads_queue": [],
        "current_index": 0,
        "current_item": {},
        "researched_person": "",
        "researched_role": "",
        "researched_city": "",
        "researched_profile": "",
        "contact_data": {},
        "results": [],
        "google_client": None,
    })

    print("\n" + "=" * 60)
    print(f"  WORKFLOW COMPLETE — {len(final_state['results'])} verified leads captured")
    print("=" * 60)
    for i, lead in enumerate(final_state["results"], 1):
        print(f"  {i}. [{lead['category']}] {lead['organization_name']} ({lead['location']})")
        print(f"     Contact: {lead['contact_person']}")
        print(f"     Channel: {lead['contact_channel']} [{lead['verification_status']}]")
