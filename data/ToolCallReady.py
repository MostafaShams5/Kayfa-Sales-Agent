import json
import re
from pathlib import Path
from typing import List, Dict, Any

class KayfaDataCompiler:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.json_dir = self.data_dir / 'json'
        self.text_dir = self.data_dir / 'text'
        self.output_dir = self.data_dir / 'processed'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.courses: List[Dict[str, Any]] = []
        self.roadmaps: List[Dict[str, Any]] = []
        
    def _normalize_string(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r'[^a-z0-9]', '', text.lower().strip())

    def _load_json(self, filename: str) -> List[Dict[str, Any]]:
        filepath = self.json_dir / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save_json(self, data: Any, filename: str) -> None:
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _parse_markdown_table(self, filename: str) -> List[Dict[str, str]]:
        filepath = self.text_dir / filename
        results = []
        if not filepath.exists():
            return results

        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        headers = []
        for line in lines:
            line = line.strip()
            if not line.startswith('|') or not line.endswith('|'):
                continue
                
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            
            if all(re.match(r'^:?-+:?$', c) for c in cells):
                continue
                
            if not headers:
                headers = [self._normalize_string(c) for c in cells]
                continue
                
            if len(cells) == len(headers):
                results.append(dict(zip(headers, cells)))
                
        return results

    def _parse_diploma_markdown(self, filepath: Path) -> Dict[str, Any]:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        diploma_data = {
            "id": filepath.stem.lower(),
            "name": "",
            "pitch": "",
            "curriculum_highlights": [],
            "career_growth": [],
            "trust_signals": [],
            "closing_value": ""
        }

        name_match = re.search(r'#\s*.*?(Product:\s*)?([^\n]+)', content)
        if name_match:
            diploma_data["name"] = name_match.group(2).strip()

        pitch_match = re.search(r'\*\*Pitch:\*\*\s*([^\n]+)', content)
        if pitch_match:
            diploma_data["pitch"] = pitch_match.group(1).strip()

        closing_match = re.search(r'\*\*Closing Value:\*\*\s*"?([^"\n]+)"?', content)
        if closing_match:
            diploma_data["closing_value"] = closing_match.group(1).strip()

        sections = re.split(r'##\s+', content)
        for section in sections:
            lines = section.strip().split('\n')
            if not lines:
                continue
            title = lines[0].lower()
            bullets = [re.sub(r'^\*\s+', '', line).strip() for line in lines[1:] if line.strip().startswith('*')]
            
            if 'stack' in title or 'curriculum' in title:
                diploma_data["curriculum_highlights"] = bullets
            elif 'career' in title or 'growth' in title:
                diploma_data["career_growth"] = bullets
            elif 'authority' in title or 'trust' in title:
                diploma_data["trust_signals"] = bullets

        return diploma_data

    def load_base_data(self) -> None:
        self.courses = self._load_json('kayfa_courses.json')
        self.roadmaps = self._load_json('kayfa_roadmaps.json')

    def enrich_courses(self) -> None:
        paid_courses = self._parse_markdown_table('kayfa_paid_individual_courses.md')
        free_courses = self._parse_markdown_table('kayfa_free_educational_content.md')

        course_enrichment = {}
        
        for pc in paid_courses:
            name_key = next((k for k in pc.keys() if 'course' in k or 'name' in k), None)
            price_key = next((k for k in pc.keys() if 'price' in k), None)
            inst_key = next((k for k in pc.keys() if 'instructor' in k), None)
            
            if not name_key:
                continue
                
            name_norm = self._normalize_string(pc.get(name_key, ''))
            price_str = pc.get(price_key, '') if price_key else ''
            clean_price = re.sub(r'[^\d.]', '', price_str)
            
            course_enrichment[name_norm] = {
                'price': float(clean_price) if clean_price else 0.0,
                'currency': 'USD',
                'instructor': pc.get(inst_key, '') if inst_key else '',
                'is_free': False
            }

        for fc in free_courses:
            name_key = next((k for k in fc.keys() if 'course' in k or 'name' in k), None)
            inst_key = next((k for k in fc.keys() if 'instructor' in k), None)
            
            if not name_key:
                continue
                
            name_norm = self._normalize_string(fc.get(name_key, ''))
            course_enrichment[name_norm] = {
                'price': 0.0,
                'currency': 'USD',
                'instructor': fc.get(inst_key, '') if inst_key else '',
                'is_free': True
            }

        for course in self.courses:
            name_norm = self._normalize_string(course.get('name', ''))
            
            is_inherently_free = any(t in course.get('id', '').lower() for t in ['tip', 'free'])
            
            enrichment_data = course_enrichment.get(name_norm, {
                'price': 0.0 if is_inherently_free else None,
                'currency': 'USD',
                'instructor': None,
                'is_free': True if is_inherently_free else None
            })
            course.update(enrichment_data)

    def enrich_roadmaps(self) -> None:
        paid_tracks = self._parse_markdown_table('kayfa_paid_educational_tracks.md')
        
        track_enrichment = {}
        for pt in paid_tracks:
            name_key = next((k for k in pt.keys() if 'track' in k or 'name' in k), None)
            price_key = next((k for k in pt.keys() if 'price' in k), None)
            
            if not name_key:
                continue
                
            name_norm = self._normalize_string(pt.get(name_key, ''))
            price_str = pt.get(price_key, '') if price_key else ''
            clean_price = re.sub(r'[^\d.]', '', price_str)
            
            track_enrichment[name_norm] = {
                'price': float(clean_price) if clean_price else 0.0,
                'currency': 'USD'
            }

        for roadmap in self.roadmaps:
            name_norm = self._normalize_string(roadmap.get('name', ''))
            
            # RULE: Diplomas/Bootcamps do not have standard track pricing. 
            # They require contacting sales.
            if 'diploma' in name_norm or 'bootcamp' in name_norm:
                roadmap.update({'price': None, 'currency': 'USD'})
                continue
            
            # For regular on-demand tracks, do the loose match
            search_name = name_norm.replace('track', '')
            matched_data = {'price': None, 'currency': 'USD'}
            
            for key, data in track_enrichment.items():
                key_search = key.replace('track', '')
                if key_search and (key_search in search_name or search_name in key_search):
                    matched_data = data
                    break
                    
            roadmap.update(matched_data)
    def process_diplomas(self) -> None:
        diplomas = []
        for filepath in self.text_dir.glob('*_diploma.md'):
            diploma_data = self._parse_diploma_markdown(filepath)
            diplomas.append(diploma_data)
            
        for filepath in self.text_dir.glob('*_Diploma.md'):
            diploma_data = self._parse_diploma_markdown(filepath)
            diplomas.append(diploma_data)

        if diplomas:
            self._save_json(diplomas, 'kayfa_diplomas_enriched.json')

    def compile_policies(self) -> None:
        policies = {
            "company_overview": self._read_text_file('kayfa_company_overview.md'),
            "faqs_and_rules": self._read_text_file('kayfa_policies_and_faqs.md'),
            "privacy": self._read_text_file('kayfa_privacy_policy.md')
        }
        self._save_json(policies, 'kayfa_policies_compiled.json')

    def _read_text_file(self, filename: str) -> str:
        filepath = self.text_dir / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return ""

    def save_enriched_catalogs(self) -> None:
        self._save_json(self.courses, 'kayfa_courses_enriched.json')
        self._save_json(self.roadmaps, 'kayfa_roadmaps_enriched.json')

    def run_pipeline(self) -> None:
        self.load_base_data()
        self.enrich_courses()
        self.enrich_roadmaps()
        self.process_diplomas()
        self.compile_policies()
        self.save_enriched_catalogs()

if __name__ == "__main__":
    compiler = KayfaDataCompiler(data_dir=".")
    compiler.run_pipeline()
