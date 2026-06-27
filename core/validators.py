import re
from typing import Dict, Any

def validate_and_format_phone(phone: str) -> Dict[str, Any]:
    cleaned = re.sub(r'\D', '', phone)

    regions = {
        "Egypt": {
            "prefixes": ["201", "01", "1"], 
            "lengths": [12, 11, 10], 
            "format": lambda x: f"20{x[-10:]}", 
            "nationality": "Egyptian"
        },
        "Saudi Arabia": {
            "prefixes": ["9665", "05", "5"], 
            "lengths": [12, 10, 9], 
            "format": lambda x: f"966{x[-9:]}", 
            "nationality": "Saudi"
        },
        "Syria": {
            "prefixes": ["9639", "09", "9"], 
            "lengths": [12, 10, 9], 
            "format": lambda x: f"963{x[-9:]}", 
            "nationality": "Syrian"
        },
        "United Arab Emirates": {
            "prefixes": ["9715", "05"], 
            "lengths": [12, 10], 
            "format": lambda x: f"971{x[-9:]}", 
            "nationality": "Emirati"
        }
    }

    for country, rules in regions.items():
        for prefix, length in zip(rules["prefixes"], rules["lengths"]):
            if cleaned.startswith(prefix) and len(cleaned) == length:
                return {
                    "is_valid": True,
                    "formatted_number": f"+{rules['format'](cleaned)}",
                    "country": country,
                    "nationality": rules["nationality"],
                    "error_message": ""
                }

    if phone.strip().startswith('+') or phone.strip().startswith('00'):
        core_number = cleaned.lstrip('0')
        if len(core_number) >= 10:
            return {
                "is_valid": True,
                "formatted_number": f"+{core_number}",
                "country": "International",
                "nationality": "International",
                "error_message": ""
            }

    return {
        "is_valid": False,
        "formatted_number": "",
        "country": "",
        "nationality": "",
        "error_message": "Invalid phone number format. Please provide a valid number including the country code."
    }

def validate_email(email: str) -> Dict[str, Any]:
    if not email or not isinstance(email, str):
        return {
            "is_valid": False,
            "email": "",
            "error_message": "Email address cannot be empty."
        }
        
    email = email.strip().lower()
    regex = r'^[a-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&\'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$'
    
    if re.match(regex, email):
        return {
            "is_valid": True,
            "email": email,
            "error_message": ""
        }
        
    return {
        "is_valid": False,
        "email": "",
        "error_message": "Invalid email address format. Please check for typos."
    }
