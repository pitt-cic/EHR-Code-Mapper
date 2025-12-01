#!/usr/bin/env python3
import json
import boto3
import pandas as pd
import os

def process_vectors():
    # Get file path from user with retry
    while True:
        file_path = input("Enter the path to your CSV file (or 'q' to quit): ").strip()
        
        if file_path.lower() == 'q':
            print("Exiting.")
            return
        
        if not os.path.exists(file_path):
            print(f"Error: File {file_path} does not exist. Try again.")
            continue
        
        if not file_path.lower().endswith('.csv'):
            print("Error: File must be a CSV file. Try again.")
            continue
        
        break
    
    # Initialize clients
    bedrock_client = boto3.client('bedrock-runtime', region_name="us-east-1")
    s3vectors = boto3.client("s3vectors", region_name="us-east-1")
    
    vector_bucket_name = 'code-mapping-vector-bucket'
    index_name = 'code-mapping-vector-index'
    
    try:
        # Read CSV from local file
        df = pd.read_csv(file_path)
        print(f"Read CSV with {len(df)} rows")
        
        # Process data in batches of 100
        batch_size = 100
        total_processed = 0
        
        for i in range(0, len(df), batch_size):
            batch_df = df.iloc[i:i+batch_size]
            vectors_batch = []
            
            for _, row in batch_df.iterrows():
                # Embed STANDARD_DISPLAY using Titan
                embedding_response = bedrock_client.invoke_model(
                    modelId='amazon.titan-embed-text-v2:0',
                    body=json.dumps({
                        'inputText': row['STANDARD_DISPLAY']
                    })
                )
                
                embedding_data = json.loads(embedding_response['body'].read())
                vector = embedding_data['embedding']
                
                # Prepare vector with metadata
                vector_item = {
                    'key': str(row['STANDARD_IDENTIFIER']),
                    'data': {'float32': vector},
                    'metadata': {
                        'code': str(row['STANDARD_IDENTIFIER']),
                        'display': str(row['STANDARD_DISPLAY']),
                        'system': str(row['SYSTEM']),
                        'rank': str(row['RANK'])
                    }
                }
                vectors_batch.append(vector_item)
            
            # Insert batch into vector index
            s3vectors.put_vectors(
                vectorBucketName=vector_bucket_name,
                indexName=index_name,
                vectors=vectors_batch
            )
            
            total_processed += len(vectors_batch)
            print(f"Processed batch {i//batch_size + 1}, total vectors: {total_processed}")
        
        print(f"Successfully processed {total_processed} vectors")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR: {str(e)}")
        print(f"TRACEBACK: {error_details}")

if __name__ == "__main__":
    process_vectors()