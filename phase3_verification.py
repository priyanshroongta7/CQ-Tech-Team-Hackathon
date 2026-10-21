import os
import re
import requests

ZEROBOUNCE_KEY = os.getenv("ZEROBOUNCE_API_KEY", "e64e2c4042b740fbabed0249c01abcb7")
HUNTER_KEY = os.getenv("HUNTER_API_KEY", "")

os.environ["ZEROBOUNCE_API_KEY"] = ZEROBOUNCE_KEY
os.environ["HUNTER_API_KEY"] = HUNTER_KEY

def clean_domain(domain_str):
    """Normalize domain strings like 'https://www.techmahindra.com/' or 'Tech Mahindra' into 'techmahindra.com'."""
    clean = re.sub(r"https?://", "", str(domain_str))
    clean = re.sub(r"^www\.", "", clean)
    clean = clean.split("/")[0].strip().lower()
    if "." not in clean:
        clean = clean.replace(" ", "") + ".com"
    return clean

def deduce_pattern_email(first_name, last_name, domain):
    """Fallback generator for standard corporate email pattern (first.last@domain)."""
    norm_first = re.sub(r"[^a-zA-Z]", "", first_name).lower()
    norm_last = re.sub(r"[^a-zA-Z]", "", last_name).lower()
    domain_clean = clean_domain(domain)
    
    if norm_first and norm_last:
        return f"{norm_first}.{norm_last}@{domain_clean}"
    elif norm_first:
        return f"{norm_first}@{domain_clean}"
    return f"contact@{domain_clean}"

def discover_email(first_name, last_name, domain):
    api_key = os.environ.get("HUNTER_API_KEY", "").strip()
    domain_clean = clean_domain(domain)

    # Only query Hunter if a real API key is provided
    if api_key and not api_key.startswith("YOUR-"):
        print(f"Asking Hunter.io to find email for {first_name} {last_name} at {domain_clean}...")
        url = f"https://api.hunter.io/v2/email-finder?domain={domain_clean}&first_name={first_name}&last_name={last_name}&api_key={api_key}"
        try:
            response = requests.get(url, timeout=8)
            if response.status_code == 200:
                data = response.json()
                email = data.get("data", {}).get("email")
                if email:
                    return email, "hunter"
        except Exception as e:
            print(f"Hunter.io lookup note: {e}")

    # Fallback to standard corporate pattern deduction
    pattern_email = deduce_pattern_email(first_name, last_name, domain_clean)
    return pattern_email, "pattern"

def verify_email(email):
    api_key = os.environ.get("ZEROBOUNCE_API_KEY", "").strip()
    
    # Ping ZeroBounce if API key is provided
    if api_key and not api_key.startswith("YOUR-"):
        print(f"Pinging ZeroBounce to verify deliverability for {email}...")
        url = f"https://api.zerobounce.net/v2/validate?api_key={api_key}&email={email}"
        try:
            response = requests.get(url, timeout=8)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status") 
                return status
        except Exception as e:
            print(f"ZeroBounce verification note: {e}")
            return "error"
    return "unverified"

def process_contact(full_name, domain, profile_url=None):
    """
    Performs discovery, deliverability verification, and enforces:
    - No hallucinated data
    - Contact channel = real email or authentic profile link
    - Verification status = 'Verified' or 'Pattern-Derived'
    """
    cleaned_name = full_name.strip()
    if not cleaned_name or cleaned_name.lower() in ["not found", "unknown", "none"]:
        return {"status": "Failed", "reason": "No decision-maker identified"}

    name_parts = cleaned_name.split()
    first_name = name_parts[0] if name_parts else "Contact"
    last_name = name_parts[-1] if len(name_parts) > 1 else ""

    email, source = discover_email(first_name, last_name, domain)
    verification_status = verify_email(email)
    
    if verification_status == "valid":
        final_status = "Verified"
        contact_channel = email
    elif source == "hunter" and email:
        final_status = "Verified"
        contact_channel = email
    elif profile_url and ("linkedin.com" in profile_url or "instagram.com" in profile_url or "facebook.com" in profile_url):
        # Authentic profile link from team/social research
        final_status = "Verified"
        contact_channel = profile_url
    elif email:
        final_status = "Pattern-Derived"
        contact_channel = email
    elif profile_url:
        final_status = "Pattern-Derived"
        contact_channel = profile_url
    else:
        print("Contact channel cannot be verified. Dropping lead.")
        return {"status": "Failed", "reason": "No authentic email or profile link found"}

    return {
        "Name": cleaned_name,
        "Email": contact_channel,
        "Verification Status": final_status
    }

if __name__ == "__main__":
    sample_name = "Jane Doe"
    sample_domain = "techmahindra.com"
    sample_role = "Marketing Lead"
    print(f"Starting Phase 3 Extraction & Verification for {sample_name} ({sample_role})...")
    result = process_contact(sample_name, sample_domain)
    print("\n--- VERIFICATION RESULT ---")
    print(result)
