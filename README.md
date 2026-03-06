# ProjectMedDial 🩺

A comprehensive platform for simulating and evaluating medical dialogues, focusing on realism, safety, and adherence to medical standards. This project aims to enhance the quality and safety of AI-driven medical consultations by providing tools for dialogue generation, annotation, and validation. 🚀


## Table of Contents 📑

- [Project Title & Badges](#projectmeddial-)
- [Description](#description-)
- [Table of Contents](#table-of-contents-)
- [Features](#features-)
- [Tech Stack](#tech-stack-)
- [Installation](#installation-)
- [Usage](#usage-)
- [Project Structure](#project-structure-)
- [API Reference](#api-reference-)
- [Contributing](#contributing-)
- [License](#license-)
- [Important Links](#important-links-)
- [Footer](#footer-)

## Features ✨

- **Dialogue Simulation**: Simulates doctor-patient conversations using sophisticated agent models. 🗣️
- **Annotation**: Annotates dialogues using the ReMeDi framework, identifying intents, actions, and medical slots. ✍️
- **Realistic Dialogue Generation**: Includes features like empathetic responses, systematic medical inquiry, and natural conversation flow for creating realistic medical dialogues. 🌿
- **Advanced Validation**: Validates medical accuracy, clinical coherence, and dialogue safety using MIMIC-III knowledge base and LLM-based assessments. ✅
- **Quality Assessment**: Provides comprehensive quality scores for generated dialogues and annotations, including completeness, accuracy, consistency, and medical relevance. 💯
- **SOTA (State of The Art) Evaluation**: Uses the coach agent (summarizer_agent, validator_agent) to evaluate the generated dialogs. 
- **GTMF (Ground Truth Medical Form) Extraction**: Utilizes Azure AI to extract key information from medical notes, structuring it for analysis. 📝
- **Progressive Disclosure**: Simulates gradual information disclosure from patients for more realistic interactions.
- **Medical Vocabulary Enhancement**: Improves semantic scores by replacing common words with medical equivalents. 📚

## Tech Stack 💻

- **Python**: Primary programming language. 🐍
- **Markdown**: Used for documentation. 📝
- **JSON**: Used for data serialization and configuration.
- **Transformers**: Utilized for advanced NLP tasks. 🧠
- **Torch**: Used for tensor computations.
- **Pydantic**: Used for data validation and settings management.
- **SQLAlchemy**: Used for database interactions (MIMIC-III).
- **Azure AI Services**: Leveraged for language model functionalities and evaluations. ☁️
- **NLTK (Natural Language Toolkit)**: Used for text processing and tokenization.
- **Sentence Transformers**: Used for calculating sentence embeddings and semantic similarity.
- **Scikit-learn**: Utilized for machine learning tasks.
- **dotenv**: Used for loading environment variables from a `.env` file.

## Installation 🛠️

1. **Clone the Repository**: ⬇️
   ```bash
   git clone https://github.com/alongott15/ProjectMedDial
   cd ProjectMedDial
   ```

2. **Create a Virtual Environment**: virtualenv is used in this project.
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Linux and macOS
   venv\Scripts\activate  # On Windows
   ```

3. **Install Dependencies**: ⚙️
   ```bash
   pip install -r requirements.txt
   ```
   Based on the `requirements.txt` file, the following packages are required:
   ```text
   transformers>=4.30.0
   torch>=2.0.0        
   pydantic>=1.10.2
   sqlalchemy>=1.4.0
   scikit-learn>=1.2.0
   sentence-transformers # New SOTA validator
   azure-ai-inference # New for GTMFAgent
   python-dotenv
   nltk
   rouge-score
   ```

4. **Configure Azure AI Credentials**: 🔑
   - Set the `AZURE_AI_ENDPOINT` and `AZURE_AI_API_KEY` environment variables. This can be done by creating a `.env` file in the project root:
     ```text
     AZURE_AI_ENDPOINT=your_azure_ai_endpoint
     AZURE_AI_API_KEY=your_azure_ai_api_key
     DATABASE_URL=your_database_url
     ```

5. **Configure MIMIC-III Database Connection**: ⚙️
   - Set the `DATABASE_URL` environment variable to your MIMIC-III database connection string.
     ```text
     DATABASE_URL=postgresql://user:password@host:port/database
     ```

## Usage 🚀

1. **Run Dialogue Simulation**: 🗣️
   - Execute `dialogue_main.py` to generate medical dialogues. The simulation leverages patient and doctor agents, and their interaction is evaluated using a coach agent. 
     ```bash
     python dialogue_main.py
     ```

2. **Run Annotation Process**: ✍️
   - Execute `annotation_main.py` to annotate the generated dialogues using the ReMeDi framework. This script processes dialogue files and annotates them with relevant medical information.
     ```bash
     python annotation_main.py
     ```

3. **Validate Annotations**: ✅
   - Run `annotation_validation.py` to validate the annotations using a realistic scoring system that includes medical validation and safety assessments. This step ensures the quality and reliability of the annotations.
     ```bash
     python annotation_validation.py
     ```

### Key Use Cases:

- **Improving AI-driven Medical Consultations**: Validating and refining AI systems used in medical consultations by simulating dialogues and identifying areas for improvement.
- **Enhancing Medical Training**: Providing realistic scenarios for medical training and education, where students can practice communication and diagnostic skills.
- **Generating High-Quality Annotated Data**: Creating a dataset of annotated medical dialogues for training and evaluating NLP models in the medical domain.

### Example Scenario:

A researcher wants to create a dataset of high-quality annotated medical dialogues. They use `dialogue_main.py` to generate dialogues, then use `annotation_main.py` to annotate them. Finally, they use `annotation_validation.py` to validate and refine the annotations, ensuring the dataset is accurate and reliable.

## Project Structure 📂

```
ProjectMedDial/
├── Agents/
│   ├── AnnotatorAgent.py       # Agent for annotating dialogues
│   ├── CoachAgent.py           # Agent for evaluating dialogue quality
│   ├── DoctorAgent.py          # Agent simulating a doctor
│   ├── GTMFAgent.py            # Agent for extracting medical information
│   ├── PatientAgent.py         # Agent simulating a patient
│   └── SummarizerAgent.py      # Agent for summarizing dialogues
│   └── ValidatorAgent.py       # Agent for validating medical extractions
├── Models/
│   ├── classes.py              # Data classes for medical entities
│   └── labels.py               # Data classes for ReMeDi annotations
├── Utils/
│   ├── llms_utils.py           # Utility functions for interacting with LLMs
│   ├── medical_validation.py   # Functions for validating medical content
│   ├── partial_profile.py      # Functions for generating partial patient profiles
│   ├── utils.py                # General utility functions
│   ├── gtmf_extractor.py       # utility for gtmf extractions
│   └── medical_knowledge_mimic.py # Enhanced Medical Knowledge Base using MIMIC-III structured data and medical ontologies
│   └── medical_validator.py  # Advanced Medical Validation using established clinical NLP metrics
├── gtmf/
│   ├── gtmf_example.json       # Example GTMF data
├── output_annotated/         # Where annotated dialogue files are stored
├── output_dialogue/            # Where simulated dialogue files are stored
├── annotation_main.py        # Main script for annotating dialogues
├── annotation_validation.py  # Main script for validating annotations
├── convert.py                # Script to convert JSON data to DataFrame format and export to Excel
├── dialogue_main.py          # Main script for generating dialogues
├── README.md                 # This file
└── requirements.txt          # Project dependencies
```

## API Reference 📚

### `AzureAIFoundryClient`

- **`chat_generate(llm: AzureAIFoundryClient, messages: List[Dict[str, str]]) -> str`**: Generates chat completions using Azure AI Foundry.
  - `llm` (AzureAIFoundryClient): The Azure AI Foundry client instance.
  - `messages` (List[Dict[str, str]]): A list of message dictionaries with `role` and `content` keys.
  - Returns: The generated text content from the LLM. 💬

### `GTMFExtractionAgent`

- **`extract(medical_text: str, use_llm_judge: bool = None) -> GTMF`**: Extracts GTMF (Ground Truth Medical Form) data from medical text.
  - `medical_text` (str): The medical text to extract from.
  - `use_llm_judge` (bool, optional): Whether to use LLM judge for assessment. Defaults to `None`.
  - Returns: The extracted GTMF instance. 📝

### `ValidatorAgent`

- **`evaluate(ground_truth: dict, conversation_info: dict)`**: Validates generated dialogues and extracts evaluation metrics.
  - `ground_truth` (dict): Ground truth data for comparison.
  - `conversation_info` (dict): Information about the generated conversation.
  - Returns: A dictionary containing validation metrics and insights. ✅

## Contributing 🤝

We welcome contributions to ProjectMedDial! To contribute:

1. Fork the repository. 🍴
2. Create a new branch for your feature or bug fix. 🌿
3. Implement your changes and add tests. ✅
4. Submit a pull request. 🚀

## License 📜

This project has no license. ⛔

## Important links 🔗

- Project Repository : [ProjectMedDial](https://github.com/alongott15/ProjectMedDial)

## Footer 🦶

© 2024 ProjectMedDial. Powered by [ProjectMedDial](https://github.com/alongott15/ProjectMedDial). Fork it, like it, raise issues and contribute to improve the project.


---
**<p align="center">Generated by [ReadmeCodeGen](https://www.readmecodegen.com/)</p>**