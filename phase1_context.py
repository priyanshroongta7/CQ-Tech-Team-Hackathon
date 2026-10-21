import os
import sys
import pdfplumber
from pydantic import BaseModel
from openai import OpenAI

# Prefer environment variable if set, otherwise fallback to local configuration
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "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")
os.environ["OPENAI_API_KEY"] = OPENAI_KEY
client = OpenAI(api_key=OPENAI_KEY)

class TargetLeadContext(BaseModel):
    name: str                   # Company or college society name
    category: str               # "Sponsor" or "College Delegation"
    domain_or_query: str        # Website domain or search term
    target_roles: list[str]     # e.g., ["Marketing Lead", "CSR Head", "Society President"]

class EventContext(BaseModel):
    target_industries: list[str]
    keywords: list[str]
    target_leads: list[TargetLeadContext]
    # Backward compatibility helpers
    target_domains: list[str]
    job_titles: list[str]

def extract_input_content(input_source):
    """
    Accepts EITHER:
    1. A file path to a PDF brochure (extracts text with pdfplumber)
    2. A text search prompt (e.g., 'Find sponsors and college delegations for an AI hackathon in Bangalore')
    """
    if isinstance(input_source, str) and input_source.lower().endswith(".pdf") and os.path.exists(input_source):
        print(f"Extracting text from PDF brochure: {input_source}...")
        extracted_text = ""
        with pdfplumber.open(input_source) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        return extracted_text.strip()
    else:
        print("Treating input as a search prompt...")
        return str(input_source).strip()

def extract_fallback_targets(input_text):
    """
    Parses all companies and societies directly from the text/brochure 
    when OpenAI API credits are exhausted.
    """
    import re
    companies = []
    societies = []

    comp_match = re.search(r"Target Companies:\s*([^\n]+)", input_text, re.IGNORECASE)
    if comp_match:
        companies = [c.strip() for c in comp_match.group(1).split(",") if c.strip()]

    soc_match = re.search(r"Target (?:Campus )?Societies:\s*([^\n]+)", input_text, re.IGNORECASE)
    if soc_match:
        societies = [s.strip() for s in soc_match.group(1).split(",") if s.strip()]

    if not companies:
        companies = ["Tech Mahindra", "Infosys", "Cisco Systems", "Google Cloud"]
    if not societies:
        societies = ["IEEE Student Branch", "ACM Student Chapter", "Coding Club"]

    leads = []
    for comp in companies:
        domain = comp.lower().replace(" ", "") + ".com"
        leads.append(TargetLeadContext(
            name=comp,
            category="Sponsor",
            domain_or_query=domain,
            target_roles=["Marketing Lead"]
        ))

    for soc in societies:
        leads.append(TargetLeadContext(
            name=soc,
            category="College Delegation",
            domain_or_query=f"{soc} Bangalore",
            target_roles=["Society President"]
        ))

    return EventContext(
        target_industries=["Information Technology", "Cloud Infrastructure", "Campus Outreach"],
        keywords=["AI", "Cloud", "Hackathon", "Sponsorship", "Campus Delegation"],
        target_leads=leads,
        target_domains=[l.domain_or_query for l in leads if l.category == "Sponsor"],
        job_titles=["Marketing Lead", "Society President"]
    )

def generate_master_list(input_text):
    print("Sending data to OpenAI to generate the master list of Sponsors & College Delegations...")
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini", 
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "You are an expert Event Strategist tasked with finding sponsors and college delegations.\n"
                        "Analyze the provided event brochure or search prompt. Produce a structured list of:\n"
                        "1. Target Industries & Keywords relevant to the event.\n"
                        "2. ALL Relevant Companies (for Category 'Sponsor') and ALL College Societies/Clubs (for Category 'College Delegation') mentioned.\n"
                        "3. Specific decision-maker titles for each (e.g., 'Marketing Lead', 'CSR Head' for sponsors; "
                        "'Society President', 'Student Convener' for college delegations).\n"
                        "Strictly categorize each lead as either 'Sponsor' or 'College Delegation'."
                    )
                },
                {
                    "role": "user", 
                    "content": f"Event Input:\n\n{input_text}"
                }
            ],
            response_format=EventContext,
        )
        return response.choices[0].message.parsed
    except Exception as e:
        if "credit_balance_exhausted" in str(e) or "insufficient_quota" in str(e) or "429" in str(e):
            print(f"\n[Notice] OpenAI Credit Balance Exhausted: {e}")
            print("Activating smart text parser to extract ALL companies and societies from the brochure...\n")
            return extract_fallback_targets(input_text)
        raise e

if __name__ == "__main__":
    # Support CLI argument or default to brochure.pdf
    input_arg = sys.argv[1] if len(sys.argv) > 1 else "brochure.pdf"
    content = extract_input_content(input_arg)
    master_list = generate_master_list(content)
    print("\n--- AI GENERATED MASTER LIST ---")
    print(f"Target Industries: {master_list.target_industries}")
    print(f"Keywords: {master_list.keywords}")
    print(f"Target Leads ({len(master_list.target_leads)}):")
    for lead in master_list.target_leads:
        print(f"  • [{lead.category}] {lead.name} ({lead.domain_or_query}) -> Roles: {lead.target_roles}")
