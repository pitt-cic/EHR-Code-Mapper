import pandas as pd
import json
from datetime import datetime

def csv_to_fhir_conceptmap(csv_path, output_path=None):
    
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Initialize ConceptMap structure with overall identifiers
    concept_map = {
        "resourceType": "ConceptMap",
        "version": "1.0.0",
        "name": "EHRCodeMappings",
        "title": "EHR Code Mappings to Standard Terminologies",
        "status": "active",
        "date": datetime.now().isoformat(),
        "publisher": "EHR Code Mapper",
        "description": "AI-generated mappings from proprietary EHR codes to LOINC and SNOMED CT",
        "property": [
            {
                "code": "preferenceRank",
                "description": "Preference rank for this mapping (1=best option, 2=second best, 3=third best)",
                "type": "integer"
            },
            {
                "code": "frequencyRank",
                "description": "Relative frequency rank in source system (-1 if unavailable)",
                "type": "integer"
            },
            {
                "code": "proprietaryCodeDataType",
                "description": "Data type of the source (proprietary) element (numerical or categorical)",
                "type": "string"
            }
        ],
        "group": []
    }
    
    # Separate groups by target system in compliance with FHIR standards
    loinc_group = {
        "source": "Proprietary Code System",
        "target": "http://loinc.org",
        "element": []
    }
    
    snomed_group = {
        "source": "Proprietary Code System", 
        "target": "http://snomed.info/sct",
        "element": []
    }
    
    # Process each row to collect all targets per proprietary code, split up by the target system
    code_data = {}
    
    # Detect format: validated (single option) or standard (3 options)
    is_validated_format = 'validated_system' in df.columns
    
    for _, row in df.iterrows():
        prop_code = str(row['prop_code'])
        prop_display = row['prop_display']
        context = row['context']
        data_type = "numerical" if "numerical" in context else "categorical"
        
        if prop_code not in code_data:
            code_data[prop_code] = {
                "display": prop_display,
                "data_type": data_type,
                "loinc_targets": [],
                "snomed_targets": []
            }
        
        # Handle validated format (single option)
        if is_validated_format:
            system = row['validated_system']
            code = row['validated_code']
            display = row['validated_display']
            rank = row['validated_rank']
            reasoning = row['validated_reasoning']
            
            if not pd.isna(system) and not pd.isna(code):
                target = {
                    "code": str(code),
                    "display": display,
                    "relationship": "equivalent",
                    "comment": reasoning,
                    "property": [{"code": "preferenceRank", "valueInteger": 1}]
                }
                
                if not pd.isna(rank) and rank != -1:
                    target["property"].append({"code": "frequencyRank", "valueInteger": int(rank)})
                
                if system == "LOINC":
                    code_data[prop_code]["loinc_targets"].append(target)
                elif system == "SNOMED CT":
                    code_data[prop_code]["snomed_targets"].append(target)
        
        # Handle standard format (3 options)
        else:
            for i in range(1, 4):
                system = row[f'option_{i}_system']
                code = row[f'option_{i}_code']
                display = row[f'option_{i}_display']
                rank = row[f'option_{i}_rank']
                reasoning = row[f'option_{i}_reasoning']
                
                if pd.isna(system) or pd.isna(code):
                    continue
                
                target = {
                    "code": str(code),
                    "display": display,
                    "relationship": "equivalent",
                    "comment": reasoning,
                    "property": [{"code": "preferenceRank", "valueInteger": i}]
                }
                
                if not pd.isna(rank) and rank != -1:
                    target["property"].append({"code": "frequencyRank", "valueInteger": int(rank)})
                
                if system == "LOINC":
                    code_data[prop_code]["loinc_targets"].append(target)
                elif system == "SNOMED CT":
                    code_data[prop_code]["snomed_targets"].append(target)
    
    # Build groups from collected data
    for prop_code, data in code_data.items():
        # Add to LOINC group if has LOINC targets
        if data["loinc_targets"]:
            element = {
                "code": prop_code,
                "display": data["display"],
                "property": [{"code": "proprietaryCodeDataType", "valueString": data["data_type"]}],
                "target": data["loinc_targets"]
            }
            loinc_group["element"].append(element)
        
        # Add to SNOMED group if has SNOMED targets
        if data["snomed_targets"]:
            element = {
                "code": prop_code,
                "display": data["display"],
                "property": [{"code": "proprietaryCodeDataType", "valueString": data["data_type"]}],
                "target": data["snomed_targets"]
            }
            snomed_group["element"].append(element)
    
    # Add non-empty groups to concept map
    if loinc_group["element"]:
        concept_map["group"].append(loinc_group)
    if snomed_group["element"]:
        concept_map["group"].append(snomed_group)
    
    # Output JSON
    if output_path is None:
        output_path = csv_path.replace('.csv', '_fhir.json')
        
    with open(output_path, 'w') as f:
        json.dump(concept_map, f, indent=2)
    
    print(f"FHIR ConceptMap saved to: {output_path}")
    return concept_map

# Create the FHIR output from the CSV file created in the mapping process
if __name__ == "__main__":
    csv_path = input("Enter the CSV file path: ").strip()
    csv_to_fhir_conceptmap(csv_path)