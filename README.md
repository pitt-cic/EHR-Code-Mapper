# EHR Code Mapper

## Index
| Section | Description |
|---------|-------------|
| [Overview](#overview) | See the motivation behind this project |
| [Demo Video](#demo-video) | Watch a demo of this project |
| [Description](#description) | Learn about the problem and our AI-driven solution |
| [Deployment](#deployment) | How to install and deploy the solution |
| [Usage](#usage) | How to use EHR Code Mapper |
| [Troubleshooting](#troubleshooting) | Common issues and solutions |
| [Bill of Materials](#bill-of-materials) | Cost of deployment and resources used |
| [Credits](#credits) | Meet the team behind this project |
| [License](#license) | See the project's license information |

## Overview

EHR Code Mapper is an AI-powered pipeline that automatically maps proprietary Electronic Health Record (EHR) codes to standardized medical terminology (LOINC and SNOMED CT). The solution leverages Amazon Bedrock's Titan Embed Text v2 and Claude Sonnet 4.5 to intelligently match custom healthcare codes with industry-standard codes, enabling researchers to focus on analysis rather than manual code mapping.

This project was developed to address a critical challenge in healthcare data interoperability. Healthcare organizations use proprietary codes to document medical tests, procedures, and observations. When researchers need to analyze data from multiple healthcare systems that use different code sets, these proprietary codes must be mapped to standardized terminologies. Manual mapping is time-consuming, error-prone, and not an effective use of researchers' time.

The platform combines semantic similarity search using vector embeddings with AI-powered reasoning to provide accurate, explainable code mappings. For each proprietary code, the system returns the top 3 most relevant standard codes along with detailed reasoning for each match.

## Demo Video
https://github.com/user-attachments/assets/d45084ff-3509-4308-8702-a316879c05dc

## Description

### Problem Statement

Researchers face significant challenges when attempting to standardize proprietary EHR codes to industry-standard terminologies like LOINC and SNOMED CT. The manual mapping process is:

- **Time-intensive**: Each proprietary code must be researched and mapped individually
- **Error-prone**: The manual process can lead to inconsistent or incorrect mappings
- **Difficult to scale**: Organizations may have thousands of proprietary codes requiring mapping
- **Inefficient use of expertise**: Researchers' time is better spent on analysis rather than manual code mapping

Without automated solutions, researchers struggle to pool data from multiple sources, limiting their ability to conduct comprehensive analyses across different healthcare systems.

### Our Approach

EHR Code Mapper addresses these challenges through an intelligent, two-stage pipeline that combines semantic search with reasoning capabilities:

**Vector Similarity Search**: The system uses Amazon Titan Embed Text v2 to generate 1024-dimensional embeddings for both standard codes and proprietary codes. Standard codes (LOINC and SNOMED CT) are pre-processed and stored in AWS S3 Vectors, a purpose-built vector database. When a proprietary code needs mapping, the system:
- Detects acronyms and abbreviations, and expands them using Claude Sonnet
- Generates embedding for the enhanced proprietary code
- Performs cosine similarity search in S3 Vectors to retrieve the top 30 most similar standard codes
- Re-enhances the proprietary code if the initial similarity scores are poor (>0.65 distance)

**AI-Powered Reasoning**: Retrieved candidates are analyzed by Claude Sonnet 4.5 via Pydantic AI to select the top 3 matches by considering:
- Test type and clinical purpose
- The average value or set of categories associated with the proprietary code
- Semantic similarity of code descriptions
- Standard code frequency rank data to break ties between similar options (when available)

**Serverless Architecture**: The solution uses AWS S3 Vectors for vector storage and Amazon Bedrock to create embeddings and perform AI reasoning. AWS CDK deploys the vector infrastructure, while local Python scripts populate the vector bucket with standard code embeddings and run the mapping pipeline.

### Architecture Diagram

![EHR Code Mapper Architecture](EHR%20Code%20Mapper.png)

### Tech Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Amazon Web Services (AWS)** | AWS CDK | Infrastructure as code for S3 Vectors deployment |
| | Amazon Bedrock | Access to Claude Sonnet 4.5 and Titan Embeddings |
| | AWS S3 Vectors | Vector database with similarity search |
| **Backend** | Pydantic AI | Framework for building AI agent with structured outputs |
| | Pandas | Data processing and CSV handling |

## Deployment

### Prerequisites

Before deploying EHR Code Mapper, ensure you have:

- **AWS Account** - [Sign up here](https://signin.aws.amazon.com/signup?request_type=register)
- **Python 3.9+** - [Download here](https://www.python.org/downloads/)
- **Node.js (v18+)** - [Download here](https://nodejs.org/en/download) or use [nvm](https://github.com/nvm-sh/nvm)
- **AWS CDK (v2)** - Install via npm:
  ```bash
  npm install -g aws-cdk
  ```
- **AWS CLI** - [Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **Git** - [Download here](https://git-scm.com/)

### AWS Configuration

1. **Configure AWS CLI** with your credentials:
   ```bash
   aws configure
   ```
   Provide your AWS Access Key ID, Secret Access Key, AWS region (e.g., `us-east-1`), and `json` as the output format.

2. **Bootstrap CDK** (required once per AWS account/region):
   ```bash
   cdk bootstrap aws://ACCOUNT_ID/REGION
   ```
   Replace `ACCOUNT_ID` and `REGION` with your AWS account ID and region (e.g., `us-east-1`).

### Deployment Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/pitt-cic/ehr-code-mapper.git
   cd ehr-code-mapper
   ```

2. **Run the deployment script**:
   ```bash
   chmod +x ./run_mapping.sh
   ./run_mapping.sh
   ```
   Select option 1 for full setup. The script will:
   - Deploy CDK infrastructure (S3 Vectors bucket and index)
   - Set up Python virtual environment
   - Install required dependencies
   - Generate embeddings for standard codes
   - Create mappings for proprietary codes

## Usage

### Step 1: Prepare Your Data

**Standard Codes CSV** (for embedding generation):
```csv
SYSTEM,STANDARD_IDENTIFIER,STANDARD_DISPLAY,RANK
LOINC,29463-7,Body weight,44
SNOMED CT,228487000,Total time smoked (observable entity),-1
```

- `SYSTEM`: The standard code system (LOINC or SNOMED CT)
- `STANDARD_IDENTIFIER`: The unique code identifier
- `STANDARD_DISPLAY`: The human-readable description of the code
- `RANK`: Relative frequency rank if available, or -1 if unavailable

**Proprietary Codes CSV** (for mapping):
```csv
proprietary_code,proprietary_display,type,average,categories
5,Pulse Oximetry,numerical,97.64,
15,Pulse Character,categorical,,Irregular; Regular
23,Oral Care,categorical,,Complete assist; With assist; Others; Self; Refused
```

- `proprietary_code`: Unique identifier for the proprietary code
- `proprietary_display`: Description or name of the proprietary code
- `type`: Data type - either `numerical` or `categorical`
- `average`: Average value for numerical codes (empty for categorical)
- `categories`: Possible values for categorical codes, separated by semicolons (empty for numerical)

### Step 2: Run the Interactive Script

Use `run_mapping.sh` to generate embeddings and create mappings:

```bash
./run_mapping.sh
```

**Options:**
1. **Full setup** - Deploy infrastructure, generate embeddings, and create mappings
2. **Embeddings + Mapping** - Skip infrastructure deployment
3. **Just add embeddings** - Only generate and store embeddings
4. **Just create mapping** - Only perform mapping (requires existing embeddings)
5. **Quit** - Exit the script

When prompted, provide the paths to your CSV files:
- Standard codes CSV (e.g., `testFiles/common_standard_codes.csv`)
- Proprietary codes CSV (e.g., `testFiles/biomarker_transformed.csv`)

### Step 3: Review Results

Open `ehr_code_mappings.csv` to see mappings with the following columns:

- `prop_code`: Original proprietary code
- `prop_display`: Proprietary code description
- `context`: Type and metadata (numerical/categorical)
- `option_1_system`: Standard code system (LOINC/SNOMED CT)
- `option_1_code`: Standard code identifier
- `option_1_display`: Standard code description
- `option_1_rank`: Frequency rank (lower = more common, -1 = unavailable)
- `option_1_reasoning`: AI explanation for the match
- *(Repeated for options 2 and 3)*

## Troubleshooting

### CDK Deployment Failures

**Problem**: CDK deployment fails with permission errors

**Solution**:
- Ensure your AWS user has administrator access or these permissions:
  - CloudFormation full access
  - S3 full access
  - IAM role creation
- Run `cdk bootstrap` again with explicit account/region:
  ```bash
  cdk bootstrap aws://123456789012/us-east-1
  ```

### Vector Index Not Found

**Problem**: `ResourceNotFoundException` when querying vectors

**Solution**:
- Verify the vector bucket and index exist in AWS console
- Check that embeddings were successfully generated
- Ensure bucket name and index name match in both scripts:
  - Bucket: `code-mapping-vector-bucket`
  - Index: `code-mapping-vector-index`

### Throttling Errors

**Problem**: `ThrottlingException` from Bedrock

**Solution**:
- The system includes automatic retry with exponential backoff
- If errors persist, reduce batch size in `create_mapping.py`:
  ```python
  batch_size = 1  # Reduce from 3
  ```
- Request quota increase in [Service Quotas console](https://console.aws.amazon.com/servicequotas/)

### Poor Mapping Quality

**Problem**: Mappings seem inaccurate or irrelevant

**Solution**:
- Ensure standard codes CSV includes relevant codes for your domain
- Check that proprietary codes have sufficient context (type, average, categories)
- Review and adjust the AI prompt in `create_mapping.py` for your use case
- Verify embeddings were generated successfully (check CloudWatch logs)

## Bill of Materials

### Pricing Structure

#### AWS Service Pricing

| Service | Pricing Model | Use Case |
|---------|--------------|----------|
| **Amazon Bedrock - Titan Embeddings** | $0.0001/1K input tokens | Embedding generation |
| **Amazon Bedrock - Claude Sonnet 4.5** | $3.00/1M input tokens<br>$15.00/1M output tokens | AI reasoning |
| **AWS S3 Vectors** | $0.06/GB-month storage<br>$0.20/GB PUT requests<br>$0.0025/1K query requests | Vector storage & search |

### Example Cost Calculation

**Scenario**: Mapping 1,000 proprietary codes against 20,000 standard codes

#### One-Time Setup (Embedding Generation)
| Component | Calculation | Cost |
|-----------|-------------|------|
| Standard code embeddings | 20,000 codes × 50 tokens × $0.0001/1K | $0.10 |
| Vector storage (1 month) | 20,000 × 4KB × $0.06/GB | $0.005 |
| Vector PUT requests | 0.078GB × $0.20/GB | $0.02 |
| **Setup Total** | | **$0.13** |

#### Per Mapping Run (1,000 codes)
| Component | Calculation | Cost |
|-----------|-------------|------|
| Proprietary code embeddings | 1,000 × 50 tokens × $0.0001/1K | $0.005 |
| Text enhancement (20% of codes) | 200 × 500 tokens × $3.00/1M input<br>200 × 100 tokens × $15.00/1M output | $0.60 |
| Vector queries | 1,000 × $0.0025/1K | $2.50 |
| AI reasoning | 1,000 × 2,000 tokens × $3.00/1M input<br>1,000 × 300 tokens × $15.00/1M output | $10.50 |
| **Mapping Total** | | **$13.61** |

**Total Cost for 1,000 Code Mappings**: ~$13.74

For current AWS pricing, visit the [AWS Pricing Calculator](https://calculator.aws/#/).

## Credits

EHR Code Mapper is an open-source project developed by the University of Pittsburgh Health Sciences and Sports Analytics Cloud Innovation Center.

**Development Team:**
- [Gary Farrell](https://www.linkedin.com/in/gary-farrell/)

**Project Leadership:**
- Technical Lead: [Maciej Zukowski](https://www.linkedin.com/in/maciejzukowski/) - Solutions Architect, Amazon Web Services (AWS)
- Program Manager: [Kate Ulreich](https://www.linkedin.com/in/kate-ulreich-0a8902134/) - Program Leader, University of Pittsburgh Health Sciences and Sports Analytics Cloud Innovation Center

**Special Thanks:**
- [Christopher Horvat, MD, MHA, MSIT](https://www.linkedin.com/in/christopher-horvat-4a901a134/)

This project is designed and developed with guidance and support from the [Health Sciences and Sports Analytics Cloud Innovation Center, powered by AWS](https://www.digital.pitt.edu/cic).

## License

This project is licensed under the MIT License.

```
MIT License

Copyright (c) 2025 University of Pittsburgh Health Sciences and Sports Analytics Cloud Innovation Center

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
