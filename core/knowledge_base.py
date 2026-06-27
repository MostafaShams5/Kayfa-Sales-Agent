import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

class KnowledgeBase:
    def __init__(self, data_dir: str = "./data/processed"):
        self.data_dir = Path(data_dir)
        
        with open(self.data_dir / "kayfa_courses_enriched.json", "r", encoding="utf-8") as f:
            self.courses = json.load(f)
            
        with open(self.data_dir / "kayfa_roadmaps_enriched.json", "r", encoding="utf-8") as f:
            self.roadmaps = json.load(f)
            
        with open(self.data_dir / "kayfa_diplomas_enriched.json", "r", encoding="utf-8") as f:
            self.diplomas = json.load(f)
            
        with open(self.data_dir / "kayfa_policies_compiled.json", "r", encoding="utf-8") as f:
            self.policies = json.load(f)

    def search_catalog(self, query: str, max_price: Optional[float] = None, free_only: bool = False) -> List[Dict[str, Any]]:
        results_tracks = []
        results_diplomas = []
        results_courses = []
        
        cleaned_query = re.sub(r'[^\w\s]', ' ', query)
        keywords = [k.lower() for k in cleaned_query.split() if len(k.strip()) > 2]

        if not keywords:
            return []

        for diploma in self.diplomas:
            if free_only or max_price is not None:
                continue
                
            search_text = f"{diploma.get('id', '')} {diploma.get('name', '')} {diploma.get('pitch', '')}".lower()
            if any(kw in search_text for kw in keywords):
                results_diplomas.append({"type": "Diploma", "id": diploma["id"], "name": diploma["name"], "price": "Contact Sales"})

        for roadmap in self.roadmaps:
            if max_price is not None and roadmap.get("price") is not None and roadmap["price"] > max_price: 
                continue
            if free_only: 
                continue
                
            search_text = f"{roadmap.get('id', '')} {roadmap.get('name', '')} {roadmap.get('summary', '')} {' '.join(roadmap.get('skills', []))}".lower()
            if any(kw in search_text for kw in keywords):
                results_tracks.append({"type": "Track", "id": roadmap["id"], "name": roadmap["name"], "price": roadmap.get("price", "Contact Sales")})

        for course in self.courses:
            if free_only and not course.get("is_free"): 
                continue
            if max_price is not None and course.get("price") is not None and course["price"] > max_price: 
                continue
                
            search_text = f"{course.get('id', '')} {course.get('name', '')} {course.get('summary', '')} {' '.join(course.get('track', []))}".lower()
            if any(kw in search_text for kw in keywords):
                results_courses.append({"type": "Course", "id": course["id"], "name": course["name"], "price": course.get("price")})

        combined_results = results_diplomas + results_tracks + results_courses
        return combined_results[:8]

    def get_program_details(self, program_id: str) -> Dict[str, Any]:
        target_id = program_id.lower().strip()
        
        for course in self.courses:
            if target_id in course["id"].lower(): 
                return course
        for roadmap in self.roadmaps:
            if target_id in roadmap["id"].lower(): 
                return roadmap
        for diploma in self.diplomas:
            if target_id in diploma["id"].lower(): 
                return diploma
                
        return {"error": "Program ID not found. Try searching the catalog using broader English keywords."}

    def get_diploma_pitch(self, diploma_id: str) -> Dict[str, Any]:
        target_id = diploma_id.lower().strip()
        
        for diploma in self.diplomas:
            if target_id in diploma["id"].lower(): 
                return diploma
                
        return {"error": "Diploma sales pitch not found."}

    def get_policy(self, topic: str) -> str:
        topic_lower = topic.lower()
        if "refund" in topic_lower or "استرداد" in topic_lower or "faq" in topic_lower: 
            return self.policies.get("faqs_and_rules", "")
        if "privacy" in topic_lower or "خصوصية" in topic_lower: 
            return self.policies.get("privacy", "")
        return self.policies.get("company_overview", "")
