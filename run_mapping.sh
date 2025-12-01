#!/bin/bash

# Colors
CYAN='\033[0;36m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "  _____ _   _ ____     ____ ___  ____  _____   __  __    _    ____  ____  _____ ____  "
echo " | ____| | | |  _ \   / ___/ _ \|  _ \| ____| |  \/  |  / \  |  _ \|  _ \| ____|  _ \ "
echo " |  _| | |_| | |_) | | |  | | | | | | |  _|   | |\/| | / _ \ | |_) | |_) |  _| | |_) |"
echo " | |___|  _  |  _ <  | |__| |_| | |_| | |___  | |  | |/ ___ \|  __/|  __/| |___|  _ < "
echo " |_____|_| |_|_| \_\  \____\___/|____/|_____| |_|  |_/_/   \_\_|   |_|   |_____|_| \_\\"
echo ""
echo -e "==========================================${NC}"
echo ""

# Step 1: Check AWS credentials
echo -e "${CYAN}Checking AWS credentials...${NC}"
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ No AWS credentials found${NC}"
    echo -e "${YELLOW}Please configure AWS CLI first: aws configure${NC}"
    exit 1
fi
echo -e "${GREEN}✅ AWS credentials verified${NC}"
echo ""

# Step 2: Choose what to run
echo -e "${CYAN}What would you like to do?"
echo -e "(First time running the program? Select option 1)"
echo ""
echo "  1) Full setup (infrastructure + embeddings + mapping)"
echo "  2) Embeddings + Mapping (skip infrastructure)"
echo "  3) Just add embeddings"
echo "  4) Just create mapping"
echo -e "  5) Quit${NC}"
read -p "Enter choice (1/2/3/4/5): " choice
echo ""

case $choice in
    1)
        RUN_INFRA=true
        RUN_EMBEDDINGS=true
        RUN_MAPPING=true
        ;;
    2)
        RUN_INFRA=false
        RUN_EMBEDDINGS=true
        RUN_MAPPING=true
        ;;
    3)
        RUN_INFRA=false
        RUN_EMBEDDINGS=true
        RUN_MAPPING=false
        ;;
    4)
        RUN_INFRA=false
        RUN_EMBEDDINGS=false
        RUN_MAPPING=true
        ;;
    5)
        echo -e "${CYAN}Goodbye!${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac

# Step 3: Deploy infrastructure (if needed)
if [ "$RUN_INFRA" = true ]; then
    echo -e "${CYAN}Deploying CDK infrastructure...${NC}"
    cd infrastructure
    npm install
    if ! npx cdk deploy --require-approval never; then
        echo -e "${RED}❌ CDK deployment failed${NC}"
        cd ..
        exit 1
    fi
    cd ..
    echo -e "${GREEN}✅ Infrastructure deployed${NC}"
    echo ""
    
    echo -e "${CYAN}Setting up Python environment...${NC}"
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install -r requirements.txt
    echo -e "${GREEN}✅ Python environment ready${NC}"
    echo ""
fi

# Step 4: Generate embeddings (if needed)
if [ "$RUN_EMBEDDINGS" = true ]; then
    source .venv/bin/activate
    echo -e "${CYAN}Generating embeddings...${NC}"
    python3 generate_embeddings.py
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Embedding generation failed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Embeddings generated${NC}"
    echo ""
fi

# Step 5: Create mapping (if needed)
if [ "$RUN_MAPPING" = true ]; then
    source .venv/bin/activate
    echo -e "${CYAN}Creating code mappings...${NC}"
    python3 create_mapping.py
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Mapping creation failed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Mappings saved to ehr_code_mappings.csv${NC}"
    echo ""
fi

echo -e "${CYAN}=========================================="
echo -e "✅ Complete!"
echo -e "==========================================${NC}"
