"""
Curated list of Top 200+ Tech Companies (Global Tech Giants, Indian IT Leaders, Unicorns, GCCs, and AI Startups).
"""

TOP_200_TECH_COMPANIES = [
    # FAANG & Global Tech Giants
    "Google", "Microsoft", "Amazon", "Meta", "Apple", "NVIDIA", "Netflix", "Tesla", "IBM", "Oracle",
    "Salesforce", "Adobe", "Cisco", "Intel", "AMD", "Qualcomm", "SAP", "VMware", "ServiceNow", "Workday",
    "Snowflake", "Databricks", "Atlassian", "Palantir", "CrowdStrike", "Palo Alto Networks", "Fortinet", "Cloudflare",
    "Datadog", "MongoDB", "Twilio", "Stripe", "Block (Square)", "Uber", "Airbnb", "Pinterest", "Snap", "Spotify",
    "LinkedIn", "eBay", "PayPal", "Shopify", "Splunk", "ServiceNow", "Zendesk", "DocuSign", "HubSpot", "Asana",
    
    # Top Indian IT Majors & GCCs
    "Tata Consultancy Services", "Infosys", "Wipro", "HCLTech", "Tech Mahindra", "Cognizant", "LTIMindtree",
    "Persistent Systems", "Mphasis", "Hexaware", "Happiest Minds", "Coforge", "Cyient", "Zensar Technologies",
    
    # High-Growth Indian Tech Unicorns & Startups
    "Swiggy", "Zomato", "Flipkart", "Paytm", "Razorpay", "CRED", "PhonePe", "Ola", "Meesho", "Freshworks",
    "Postman", "BrowserStack", "Hasura", "Dream11", "Zerodha", "Groww", "Pine Labs", "InMobi", "CommerceIQ",
    "Chargebee", "Urban Company", "Nykaa", "Gupshup", "PhysicsWallah", "Unacademy", "ShareChat", "Cars24",
    "Lenskart", "Delhivery", "Innovaccer", "Darwinbox", "RateGain", "Sprinklr", "Zepto", "Blinkit", "KreditBee",
    
    # Global Banking, Fintech & Enterprise GCCs in India
    "Goldman Sachs", "Morgan Stanley", "J.P. Morgan", "Barclays", "HSBC", "Wells Fargo", "Deutsche Bank", "UBS",
    "Mastercard", "Visa", "American Express", "Fidelity Investments", "BlackRock", "Citadel", "Intuit", "Experian",
    "Thomson Reuters", "S&P Global", "FactSet", "Bloomberg",
    
    # Hardware, Semiconductor & Embedded Systems
    "Samsung", "Sony", "LG Electronics", "Dell Technologies", "HP Inc", "Lenovo", "Siemens", "Philips", "GE Digital",
    "Schneider Electric", "Bosch", "Texas Instruments", "Applied Materials", "Synopsys", "Cadence", "ARM", "ASML",
    "Broadcom", "Micron Technology", "Seagate", "Western Digital", "Microchip Technology", "NXP Semiconductors",
    
    # Telecom, Cloud & Networking Infrastructure
    "Juniper Networks", "Arista Networks", "Ericsson", "Nokia", "Verizon", "AT&T", "Bharti Airtel", "Reliance Jio",
    "Akamai Technologies", "DigitalOcean", "Linode", "Fastly", "Pure Storage", "NetApp", "Nutanix",
    
    # AI & Frontier Labs / Agentic Tech
    "OpenAI", "Anthropic", "Midjourney", "Cohere", "Perplexity AI", "Hugging Face", "Scale AI", "ElevenLabs",
    "Mistral AI", "DeepL", "Anyscale", "Weights & Biases", "Pinecone", "Qdrant", "Weaviate", "LangChain",
    "Together AI", "Groq", "Cerebras", "Replicant", "Jasper", "Rasa", "DataRobot", "H2O.ai",
    
    # Gaming, Media & Consumer Tech
    "Electronic Arts", "Ubisoft", "Take-Two Interactive", "Unity Technologies", "Epic Games", "Roblox", "Riot Games",
    "ByteDance", "Tencent", "NetEase", "Nintendo", "Canva", "Match Group", "Duolingo", "Coursera", "Udemy"
]

# Ensure sorted unique list
TOP_200_TECH_COMPANIES = sorted(list(dict.fromkeys(TOP_200_TECH_COMPANIES)))
