print("Starting imports...")
import boto3
import json
import pandas as pd
import asyncio
import time
import os
from concurrent.futures import ThreadPoolExecutor
from pydantic_ai import Agent
from pydantic import BaseModel
from typing import List
print("Imports complete")

class OptionResult(BaseModel):
    option: str
    reasoning: str

class MatchingResult(BaseModel):
    matches: List[OptionResult]

# Get configuration from environment or use defaults
VECTOR_BUCKET_NAME = 'code-mapping-vector-bucket'
VECTOR_INDEX_NAME = 'code-mapping-vector-index'
AWS_REGION = 'us-east-1'

# Initialize AWS clients
print("Initializing AWS clients...")
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
s3vectors = boto3.client("s3vectors", region_name=AWS_REGION)
print(f"AWS clients initialized (region: {AWS_REGION})")
print(f"Using vector bucket: {VECTOR_BUCKET_NAME}")
print(f"Using vector index: {VECTOR_INDEX_NAME}")

# Initialize agent
print("Initializing agent...")
agent = Agent(
    'bedrock:us.anthropic.claude-sonnet-4-5-20250929-v1:0',
    instructions="""You are a medical coding expert. Match the given proprietary medical code to standard codes.

TASK: Analyze the proprietary medical test and return the 3 best matching standard codes, ranked by relevance.

MATCHING PRINCIPLES:

1. **Explicit naming takes precedence:**
   - Prefixes, suffixes, and qualifiers in the source name are definitive indicators
   - These explicit terms override any inferences made from values or frequency
   - Parse every component of the source name including abbreviations and their parts
   - Frequency rank is ONLY for breaking ties between semantically equivalent options

2. **Use values to discriminate between interpretations:**
   - When choosing between unit types or specimen types, evaluate which interpretation makes the value physiologically plausible
   - Prefer interpretations where the average value falls in normal/expected ranges
   - If one interpretation would make the value pathologically extreme while another makes it normal, choose the normal interpretation
   - Average readings represent typical results, not outliers

3. **Match method and specificity exactly:**
   - If source specifies a method or characteristic, target must include it
   - If source omits a method or characteristic, prefer targets that also omit it
   - Do not infer or add methods not explicitly stated in the source

4. **Identify the primary analyte:**
   - Determine which term is the actual measurement vs contextual information
   - Some words describe what is being measured; others describe why or where
   - When categories provide concentration ranges, compare against typical values for candidate analytes to identify which is being measured

5. **Apply domain knowledge consistently:**
   - Point-of-care and bedside testing analyzes whole blood specimens directly without centrifugation
   - Categorical values describing functional status (assistance levels, ability scales) indicate observable entity codes
   - When source and target options differ only in specimen type, select based on testing context

MATCHING CRITERIA:
- Clinical purpose and test type
- Numerical ranges/averages when provided
- Category associations
- Semantic similarity of descriptions

INPUT FORMAT:
Proprietary Code: [code]
Average Value: [value] (if provided)
Categories: [categories] (if provided)
Frequency Rank: [-1 if unavailable, otherwise 1 to 20,000]

STANDARD CODE OPTIONS:
[List of Code: X, Display: Y pairs]

OUTPUT: Return exactly 3 matches in ranked order using the specified Pydantic format. For each match, provide:
- The standard code (exact match from options)
- Brief reasoning (1-2 sentences explaining the clinical/semantic match)

CRITICAL: The "option" field must contain ONLY the code with no prefixes, labels, or additional information.

Do not invent codes. Only select from the provided options.""",
    output_type=MatchingResult
)
print("Agent initialized")

def get_embedding_with_enhancement(proprietary_display, row):
    # Remove keywords from end before checking length
    cleaned_display = proprietary_display.rstrip()
    if cleaned_display.lower().endswith(' transcribed') or cleaned_display.lower().endswith('-transcribed'):
        cleaned_display = cleaned_display[:-12].rstrip()
    elif cleaned_display.lower().endswith(' old') or cleaned_display.lower().endswith('-old'):
        cleaned_display = cleaned_display[:-4].rstrip()
    
    text_to_embed = cleaned_display
    
    # Check if proprietary_display is short or an abbreviation and augment if needed
    has_capitalized_word = any(len(word) >= 3 and word.isupper() for word in cleaned_display.split())
    if len(cleaned_display) <= 5 or has_capitalized_word:
        # Build context based on type
        context = f"This is a {row['type']} field."
        if row['type'] == 'numerical':
            context += f" Average value: {row['average']}."
        elif row['type'] == 'categorical':
            context += f" Categories: {row['categories']}."
        
        claude_response = bedrock.invoke_model(
            modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{
                    "role": "user",
                    "content": f"""
We are mapping EHR codes to LOINC and SNOMED standards.

This display is short or contains acronyms: "{cleaned_display}"
Context (pediatrics): {context}

If this is an acronym, expand it using standard medical terminology. Keep it concise - add only 1-3 words maximum.

Return ONLY the expanded term, nothing else. Match LOINC/SNOMED naming conventions.

Examples:
- "CBC" → "Complete blood count"
- "BP" → "Blood pressure"
- "RBC" → "Red blood cell count"
"""
                }]
            })
        )
        claude_result = json.loads(claude_response["body"].read())
        text_to_embed = claude_result["content"][0]["text"]
        print(f"  Possible acronym detected. Enhanced to: {text_to_embed}")
    
    # Get embedding
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text_to_embed})
    )
    model_response = json.loads(response["body"].read())
    embedding = model_response["embedding"]
    
    # Query vector store
    response = s3vectors.query_vectors(
        vectorBucketName=VECTOR_BUCKET_NAME,
        indexName=VECTOR_INDEX_NAME,
        queryVector={"float32": embedding},
        topK=30,
        returnDistance=True,
        returnMetadata=True
    )
    
    # Check if best match distance is too high and retry with improved text
    if response["vectors"] and response["vectors"][0]["distance"] > 0.65:
        best_distance = response["vectors"][0]["distance"]
        # Build context based on type
        context = f"This is a {row['type']} field."
        if row['type'] == 'numerical':
            context += f" Average value: {row['average']}."
        elif row['type'] == 'categorical':
            context += f" Categories: {row['categories']}."
        
        print(f"  Poor embedding results (distance: {best_distance:.3f}). Re-enhancing...")
        
        claude_response = bedrock.invoke_model(
            modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{
                    "role": "user",
                    "content": f"""
We are mapping this EHR display to LOINC/SNOMED codes, but got poor embedding matches.

Original display: {text_to_embed}
Context (pediatrics): {context}

Return a 2-5 word phrase using standard medical terminology that matches LOINC/SNOMED naming conventions.

Focus on the core clinical concept. Avoid generic words like "documentation", "assessment", "pediatric".

Return ONLY the improved phrase, nothing else.
"""
                }]
            })
        )
        claude_result = json.loads(claude_response["body"].read())
        text_to_embed = claude_result["content"][0]["text"]
        print(f"  Re-enhanced to: {text_to_embed}")
        
        # Re-embed with improved text
        response = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": text_to_embed})
        )
        model_response = json.loads(response["body"].read())
        embedding = model_response["embedding"]
        
        # Re-query vector store
        response = s3vectors.query_vectors(
            vectorBucketName=VECTOR_BUCKET_NAME,
            indexName=VECTOR_INDEX_NAME,
            queryVector={"float32": embedding},
            topK=30,
            returnDistance=True,
            returnMetadata=True
        )
    
    best_distance = response["vectors"][0]["distance"] if response["vectors"] else None
    print(f"  Found {len(response['vectors'])} similar codes, best distance: {best_distance:.3f}")
    return response["vectors"]

def run_with_backoff(topic, max_retries=5):
    """Handle bedrock throttling with exponential backoff"""
    for attempt in range(max_retries):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(agent.run(topic))
                return result
            finally:
                loop.close()
        except Exception as e:
            if "ThrottlingException" in str(e) and attempt < max_retries - 1:
                wait_time = (2 ** attempt) + (time.time() % 1)
                print(f"Throttled, waiting {wait_time:.1f}s before retry {attempt + 1}")
                time.sleep(wait_time)
            else:
                raise e

def process_batch(batch_data):
    """Process a batch of test cases in parallel"""
    results = []
    batch_start = time.time()
    success_count = 0
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(run_with_backoff, item['topic']) for item in batch_data]
        for i, future in enumerate(futures):
            try:
                result = future.result()
                results.append({'result': result, 'metadata': batch_data[i]})
                success_count += 1
            except Exception as e:
                print(f"  Item {i+1} error: {e}")
                results.append({'result': None, 'metadata': batch_data[i]})
    batch_elapsed = time.time() - batch_start
    print(f"  Successfully processed {success_count} of {len(batch_data)} items in {batch_elapsed:.1f}s")
    return results

# Load biomarker data
while True:
    file_path = input("Enter the path to your biomarker CSV file (or 'q' to quit): ").strip()
    
    if file_path.lower() == 'q':
        print("Exiting.")
        exit(0)
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist. Try again.")
        continue
    
    if not file_path.lower().endswith('.csv'):
        print("Error: File must be a CSV file. Try again.")
        continue
    
    try:
        biomarker_df = pd.read_csv(file_path)
        print("Input data loaded")
        break
    except Exception as e:
        print(f"Error reading CSV: {e}. Try again.")
        continue

# Prepare test cases using the embedding system
print("Preparing test cases with embedding system")
test_cases = []
for idx, row in biomarker_df.iterrows():
    prop_code = str(row['proprietary_code']) if pd.notna(row['proprietary_code']) else 'N/A'
    prop_display = str(row['proprietary_display']) if pd.notna(row['proprietary_display']) else ''
    
    print(f"Processing row {idx + 1}/{len(biomarker_df)}: {prop_display}")
    
    if prop_display:
        options = get_embedding_with_enhancement(prop_display, row)
        
        if not options:
            continue
        
        # Format options for the agent
        options_text = []
        for opt in options:
            metadata = opt["metadata"]
            code = metadata["code"]
            display = metadata.get('display', 'N/A')
            rank = metadata.get('rank', '-1')
            options_text.append(f"Code: {code}, Display: {display}, Rank: {rank}.")
        
        # Build context
        context = f"Type: {row['type']}"
        if row['type'] == 'numerical':
            context += f", Average: {row['average']}"
        elif row['type'] == 'categorical':
            context += f", Categories: {row['categories']}"
        
        # Build topic for agent
        topic = f"Proprietary Code: {prop_display}\n"
        if row['type'] == 'numerical':
            topic += f"Average Value: {row['average']}\n"
        if row['type'] == 'categorical':
            topic += f"Categories: {row['categories']}\n"
        
        topic += "STANDARD CODE OPTIONS:\n" + "\n".join(options_text)
        
        test_cases.append({
            'topic': topic,
            'prop_code': prop_code,
            'prop_display': prop_display,
            'context': context,
            'options': options
        })

# Process in batches
print(f"Processing {len(test_cases)} mappings in batches of 3")
all_mappings = []
batch_size = 3

for i in range(0, len(test_cases), batch_size):
    batch = test_cases[i:i+batch_size]
    print(f"Processing batch {i//batch_size + 1}/{(len(test_cases) + batch_size - 1)//batch_size}")
    
    batch_results = process_batch(batch)
    
    for batch_result in batch_results:
        if batch_result['result'] is None:
            continue
            
        result = batch_result['result']
        metadata = batch_result['metadata']
        
        # Create one row with all 3 options
        mapping_row = {
            'prop_code': metadata['prop_code'],
            'prop_display': metadata['prop_display'],
            'context': metadata['context']
        }
        
        for i, match in enumerate(result.output.matches, 1):
            # Find the matching option to get system, rank and display
            rank = '-1'
            display = 'N/A'
            system = 'N/A'
            for opt in metadata['options']:
                if opt["metadata"]["code"] == match.option:
                    rank = opt["metadata"].get('rank', '-1')
                    display = opt["metadata"].get('display', 'N/A')
                    system = opt["metadata"].get('system', 'N/A')
                    break
            
            mapping_row[f'option_{i}_system'] = system
            mapping_row[f'option_{i}_code'] = match.option
            mapping_row[f'option_{i}_display'] = display
            mapping_row[f'option_{i}_rank'] = rank
            mapping_row[f'option_{i}_reasoning'] = match.reasoning
        
        all_mappings.append(mapping_row)

# Save mappings to CSV
mappings_df = pd.DataFrame(all_mappings)
mappings_df.to_csv('ehr_code_mappings.csv', index=False)
print(f"Mapping complete. Created {len(all_mappings)} mappings saved to 'ehr_code_mappings.csv'")