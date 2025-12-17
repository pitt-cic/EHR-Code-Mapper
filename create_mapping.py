print("Starting imports...")
import boto3
import json
import pandas as pd
import asyncio
import time
import os
import threading
from threading import Thread, Lock
from queue import Queue, Empty
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

def invoke_bedrock_with_backoff(model_id, body, max_retries=8):
    """Invoke bedrock with exponential backoff for throttling"""
    for attempt in range(max_retries):
        try:
            return bedrock.invoke_model(modelId=model_id, body=body)
        except Exception as e:
            if "ThrottlingException" in str(e) and attempt < max_retries - 1:
                wait_time = (2 ** attempt) + (time.time() % 1)
                time.sleep(wait_time)
            else:
                raise e

def get_embedding_with_enhancement(proprietary_display, row, thread_name):
    """Generate embedding for proprietary code and query vector store for similar standard codes"""
    # Remove keywords from end before checking length
    text_to_embed = proprietary_display.rstrip()
    if text_to_embed.lower().endswith(" transcribed") or text_to_embed.lower().endswith("-transcribed"):
        text_to_embed = text_to_embed[:-12].rstrip()
    elif text_to_embed.lower().endswith(" old") or text_to_embed.lower().endswith("-old"):
        text_to_embed = text_to_embed[:-4].rstrip()
    
    # Check if proprietary_display is short or an abbreviation and augment if needed
    has_capitalized_word = any(len(word) >= 3 and word.isupper() for word in text_to_embed.split())
    if len(text_to_embed) <= 5 or has_capitalized_word:
        print(f"[Thread {thread_name}]   Acronym detected, expanding...")
        # Build context based on type
        context = f"This is a {row["type"]} field."
        if row["type"] == "numerical":
            context += f" Average value: {row["average"]}."
        elif row["type"] == "categorical":
            context += f" Categories: {row["categories"]}."
        
        claude_response = invoke_bedrock_with_backoff(
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{
                    "role": "user",
                    "content": f"""
We are mapping EHR codes to LOINC and SNOMED standards.

This display is short or contains acronyms: "{text_to_embed}"
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
        print(f"[Thread {thread_name}]   Enhanced to: {text_to_embed}")
    
    # Get embedding
    print(f"[Thread {thread_name}]   Generating embedding...")
    response = invoke_bedrock_with_backoff(
        "amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text_to_embed})
    )
    model_response = json.loads(response["body"].read())
    embedding = model_response["embedding"]
    
    # Query vector store
    print(f"[Thread {thread_name}]   Querying vector store...")
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
        print(f"[Thread {thread_name}]   Poor match (distance: {best_distance:.3f}), re-enhancing...")
        # Build context based on type
        context = f"This is a {row["type"]} field."
        if row["type"] == "numerical":
            context += f" Average value: {row["average"]}."
        elif row["type"] == "categorical":
            context += f" Categories: {row["categories"]}."
        
        claude_response = invoke_bedrock_with_backoff(
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
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
        print(f"[Thread {thread_name}]   Re-enhanced to: {text_to_embed}")
        
        # Re-embed with improved text
        print(f"[Thread {thread_name}]   Re-generating embedding...")
        response = invoke_bedrock_with_backoff(
            "amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": text_to_embed})
        )
        model_response = json.loads(response["body"].read())
        embedding = model_response["embedding"]
        
        # Re-query vector store
        print(f"[Thread {thread_name}]   Re-querying vector store...")
        response = s3vectors.query_vectors(
            vectorBucketName=VECTOR_BUCKET_NAME,
            indexName=VECTOR_INDEX_NAME,
            queryVector={"float32": embedding},
            topK=30,
            returnDistance=True,
            returnMetadata=True
        )
    
    best_distance = response["vectors"][0]["distance"] if response["vectors"] else None
    print(f"[Thread {thread_name}]   Found {len(response["vectors"])} codes, best distance: {best_distance:.3f}")
    return response["vectors"]

def run_agent_with_backoff(topic, max_retries=8):
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
                time.sleep(wait_time)
            else:
                raise e

def process_item_end_to_end(row, idx, total, results_list, lock):
    """Process a single item from embedding through mapping"""
    try:
        prop_code = str(row["proprietary_code"]) if pd.notna(row["proprietary_code"]) else "N/A"
        prop_display = str(row["proprietary_display"]) if pd.notna(row["proprietary_display"]) else ""
        
        if not prop_display:
            return
        
        print(f"[Thread {threading.current_thread().name}] Processing {idx + 1}/{total}: {prop_display}")
        
        # Step 1: Get embedding and similar codes
        options = get_embedding_with_enhancement(prop_display, row, threading.current_thread().name)
        
        if not options:
            print(f"[Thread {threading.current_thread().name}] No options found for {prop_display}")
            return
        
        # Step 2: Format embedding results for mapping agent
        options_text = []
        for opt in options:
            metadata = opt["metadata"]
            code = metadata["code"]
            display = metadata.get("display", "N/A")
            rank = metadata.get("rank", "-1")
            options_text.append(f"Code: {code}, Display: {display}, Rank: {rank}.")
        
        # Build context for CSV output
        context = f"Type: {row["type"]}"
        if row["type"] == "numerical":
            context += f", Average: {row["average"]}"
        elif row["type"] == "categorical":
            context += f", Categories: {row["categories"]}"
        
        # Build topic for agent
        topic = f"Proprietary Code: {prop_display}\n"
        if row["type"] == "numerical":
            topic += f"Average Value: {row["average"]}\n"
        if row["type"] == "categorical":
            topic += f"Categories: {row["categories"]}\n"
        
        topic += "STANDARD CODE OPTIONS:\n" + "\n".join(options_text)
        
        # Step 3: Run agent to get mappings
        result = run_agent_with_backoff(topic)
        
        # Step 4: Format result
        mapping_row = {
            "prop_code": prop_code,
            "prop_display": prop_display,
            "context": context
        }
        
        for i, match in enumerate(result.output.matches, 1):
            # Find the matching option to get system, rank and display
            rank = "-1"
            display = "N/A"
            system = "N/A"
            for opt in options:
                if opt["metadata"]["code"] == match.option:
                    rank = opt["metadata"].get("rank", "-1")
                    display = opt["metadata"].get("display", "N/A")
                    system = opt["metadata"].get("system", "N/A")
                    break
            
            mapping_row[f"option_{i}_system"] = system
            mapping_row[f"option_{i}_code"] = match.option
            mapping_row[f"option_{i}_display"] = display
            mapping_row[f"option_{i}_rank"] = rank
            mapping_row[f"option_{i}_reasoning"] = match.reasoning
        
        # Step 5: Add to results (thread-safe)
        with lock:
            results_list.append(mapping_row)
        
        print(f"[Thread {threading.current_thread().name}] Completed {idx + 1}/{total}")
        
    except Exception as e:
        print(f"[Thread {threading.current_thread().name}] Error processing row {idx + 1}: {e}")

def worker_thread(work_queue, results_list, lock):
    """Worker that pulls items from queue and processes them"""
    while True:
        try:
            item = work_queue.get(timeout=1)
            if item is None:
                break
            idx, row, total = item
            process_item_end_to_end(row, idx, total, results_list, lock)
        except Empty:
            break  # Queue empty, exit
        except Exception as e:
            print(f"[{threading.current_thread().name}] Unexpected error: {e}")
            continue  # Log error but keep processing other items

# Load biomarker data
while True:
    file_path = input("Enter the path to your biomarker CSV file (or 'q' to quit): ").strip()
    
    if file_path.lower() == "q":
        print("Exiting.")
        exit(0)
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist. Try again.")
        continue
    
    if not file_path.lower().endswith(".csv"):
        print("Error: File must be a CSV file. Try again.")
        continue
    
    try:
        biomarker_df = pd.read_csv(file_path)
        print("Input data loaded")
        
        # Validate required columns
        required_columns = ["proprietary_code", "proprietary_display", "type", "average", "categories"]
        missing_columns = [col for col in required_columns if col not in biomarker_df.columns]
        if missing_columns:
            print(f"Error: Missing required columns: {', '.join(missing_columns)}")
            print("Please provide a CSV with all required columns.")
            continue
        
        break
    except Exception as e:
        print(f"Error reading CSV: {e}. Try again.")

# Prepare work distribution
num_threads = 4
total_rows = len(biomarker_df)
results = []
results_lock = Lock()
work_queue = Queue()

# Add all work items to queue
for idx, row in biomarker_df.iterrows():
    work_queue.put((idx, row, total_rows))

# Start threads
print(f"\nStarting {num_threads} parallel workers to process {total_rows} items")
start_time = time.time()

threads = []
for i in range(num_threads):
    t = Thread(target=worker_thread, args=(work_queue, results, results_lock), name=f"Worker-{i+1}")
    t.start()
    threads.append(t)

# Wait for all threads to complete
for t in threads:
    t.join()

elapsed_time = time.time() - start_time
print(f"\nAll threads completed in {elapsed_time:.1f}s")

# Save mappings to CSV
mappings_df = pd.DataFrame(results)
mappings_df.to_csv("ehr_code_mappings.csv", index=False)
print(f"Mapping complete. Created {len(results)} mappings saved to 'ehr_code_mappings.csv'")
