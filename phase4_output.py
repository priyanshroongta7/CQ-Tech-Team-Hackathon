import gspread
from typing import Literal
from pydantic import BaseModel, ValidationError, field_validator

def authenticate_google_sheets(credentials_file):
    print("Authenticating with Google Sheets API...")
    gc = gspread.service_account(filename=credentials_file)
    return gc

HEADERS = [
    "Organization Name",
    "Category",
    "Location",
    "Contact Person",
    "Contact Channel",
    "Verification Status"
]

class VerifiedLead(BaseModel):
    organization_name: str
    category: str
    location: str
    contact_person: str
    contact_channel: str
    verification_status: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        clean = v.strip().title()
        if "college" in clean.lower() or "delegation" in clean.lower() or "society" in clean.lower():
            return "College Delegation"
        return "Sponsor"

    @field_validator("verification_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if "verified" in v.lower() and "pattern" not in v.lower():
            return "Verified"
        return "Pattern-Derived"

def ensure_headers_exist(sheet):
    """Ensures Row 1 has the mandatory 6-column headers matching the problem statement."""
    try:
        first_row = sheet.row_values(1)
        if not first_row:
            sheet.append_row(HEADERS)
            print("Initialized Google Sheet with 6 mandatory header columns.")
    except Exception as e:
        print(f"Header check note: {e}")

def push_lead_to_sheet(gc, sheet_url, lead_data):
    try:
        print("Validating lead data format against mandatory 6-field schema...")
        validated_lead = VerifiedLead(**lead_data)
        
        row_to_insert = [
            validated_lead.organization_name,
            validated_lead.category,
            validated_lead.location,
            validated_lead.contact_person,
            validated_lead.contact_channel,
            validated_lead.verification_status
        ]
        
        print(f"Connecting to Google Sheet and pushing data...")
        sheet = gc.open_by_url(sheet_url).sheet1
        ensure_headers_exist(sheet)
        sheet.append_row(row_to_insert)
        
        print("Success! Verified row directly pushed to the Google Sheet.")
        return True
        
    except ValidationError as e:
        print(f"Data formatting failed. The lead did not match the mandatory schema: {e}")
        return False

if __name__ == "__main__":
    SERVICE_ACCOUNT_FILE = "credentials.json"
    GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1npEIdK2L0DXVqhzjLbucwzgpMJBK_6HQKxiLDe0dmI8/edit?gid=0#gid=0"
    
    sample_lead = {
        "organization_name": "Tech Mahindra",
        "category": "Sponsor",
        "location": "Pune",
        "contact_person": "Jane Doe - Marketing Lead",
        "contact_channel": "jane.doe@techmahindra.com",
        "verification_status": "Verified"
    }
    
    print("Starting Phase 4 Output Pipeline...")
    google_client = authenticate_google_sheets(SERVICE_ACCOUNT_FILE)
    push_lead_to_sheet(google_client, GOOGLE_SHEET_URL, sample_lead)
