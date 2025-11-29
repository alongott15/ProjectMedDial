# Agents/GTMFAgent_azure.py
import logging
import json
import os
from typing import Tuple, Optional, List, Dict
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from Models.classes import GTMF, CoreFields, ContextFields, AdditionalContext, PatientDemographics, MedicalHistory
from Utils import gtmf_extractor
from prompts.prompt_loader import get_prompt_loader
import re
from dataclasses import dataclass

# Configure logging with more detail for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('gtmf_agent.log')
    ]
)
logger = logging.getLogger(__name__)

# Enable debug logging for JSON parsing issues
debug_json = os.getenv("DEBUG_JSON", "false").lower() == "true"
if debug_json:
    logging.getLogger(__name__).setLevel(logging.DEBUG)

@dataclass
class ExtractionQualityMetrics:
    """Quality metrics for individual field extractions"""
    extraction_confidence: float  # 0-1, confidence in extraction
    text_coverage: float          # 0-1, how much of relevant text was captured
    validation_score: float       # 0-1, validation against medical knowledge
    completeness: float          # 0-1, completeness of extracted fields

@dataclass
class GTMFJudgmentScore:
    """Azure AI LLM judgment score for GTMF quality"""
    overall_score: float          # 0-10, overall quality score
    completeness_score: float     # 0-10, completeness assessment
    accuracy_score: float         # 0-10, accuracy assessment
    consistency_score: float      # 0-10, internal consistency
    medical_relevance_score: float # 0-10, medical relevance
    structure_score: float        # 0-10, structural correctness
    symptoms_quality: float       # 0-10, symptom extraction quality
    diagnoses_quality: float      # 0-10, diagnosis extraction quality
    treatments_quality: float     # 0-10, treatment extraction quality
    demographics_quality: float   # 0-10, demographics quality
    confidence_level: float       # 0-1, judge confidence in assessment
    strengths: List[str]          # List of identified strengths
    weaknesses: List[str]         # List of identified weaknesses
    critical_issues: List[str]    # Critical issues found
    recommendations: List[str]    # Improvement recommendations
    judgment_reasoning: str       # Reasoning behind the judgment

class AzureAIClient:
    """Azure AI client wrapper for GTMF operations"""
    
    def __init__(self, endpoint: str = None, api_key: str = None, model_name: str = "gpt-4", temperature: float = 0.0, max_tokens: int = 2048):
        self.endpoint = endpoint or os.getenv("AZURE_AI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_AI_API_KEY")
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        if not self.endpoint or not self.api_key:
            raise ValueError("Azure AI endpoint and API key must be provided via parameters or environment variables")
        
        self.client = ChatCompletionsClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key)
        )
    
    def chat_completion(self, system_message: str, user_message: str, temperature: float = None) -> str:
        """Generate chat completion using Azure AI"""
        try:
            response = self.client.complete(
                messages=[
                    SystemMessage(content=system_message),
                    UserMessage(content=user_message)
                ],
                model=self.model_name,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Azure AI completion failed: {e}")
            raise

def chunk_medical_text(text: str, max_chunk_size: int = 2500, overlap: int = 150) -> List[Dict[str, str]]:
    """Split medical text into overlapping chunks with section awareness"""
    if len(text) <= max_chunk_size:
        return [{"content": text, "section": "full_document"}]
    
    # Try to identify major sections first
    sections = identify_medical_sections(text)
    
    chunks = []
    if sections:
        # Process each section separately
        for section_name, section_text in sections.items():
            if len(section_text) <= max_chunk_size:
                chunks.append({"content": section_text, "section": section_name})
            else:
                # Split large sections
                section_chunks = split_text_with_overlap(section_text, max_chunk_size, overlap)
                for i, chunk_text in enumerate(section_chunks):
                    chunks.append({
                        "content": chunk_text, 
                        "section": f"{section_name}_part_{i+1}"
                    })
    else:
        # Fallback to simple chunking
        text_chunks = split_text_with_overlap(text, max_chunk_size, overlap)
        for i, chunk_text in enumerate(text_chunks):
            chunks.append({"content": chunk_text, "section": f"chunk_{i+1}"})
    
    return chunks

def identify_medical_sections(text: str) -> Dict[str, str]:
    """Identify common medical note sections"""
    sections = {}
    text_lower = text.lower()
    
    # Common medical section headers
    section_patterns = {
        "chief_complaint": [r"chief complaint:?", r"cc:?"],
        "history_present_illness": [r"history of present illness:?", r"hpi:?"],
        "past_medical_history": [r"past medical history:?", r"pmh:?"],
        "medications": [r"medications:?", r"current medications:?"],
        "allergies": [r"allergies:?", r"drug allergies:?"],
        "physical_exam": [r"physical exam:?", r"examination:?"],
        "assessment_plan": [r"assessment and plan:?", r"impression:?", r"plan:?"],
        "discharge_summary": [r"discharge summary:?", r"hospital course:?"]
    }
    
    # Find section boundaries
    section_positions = {}
    for section_name, patterns in section_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                section_positions[section_name] = match.start()
                break
    
    # Extract sections based on positions
    sorted_sections = sorted(section_positions.items(), key=lambda x: x[1])
    
    for i, (section_name, start_pos) in enumerate(sorted_sections):
        if i < len(sorted_sections) - 1:
            end_pos = sorted_sections[i + 1][1]
        else:
            end_pos = len(text)
        
        section_content = text[start_pos:end_pos].strip()
        if section_content:
            sections[section_name] = section_content
    
    return sections

def split_text_with_overlap(text: str, max_size: int, overlap: int) -> List[str]:
    """Split text into chunks with overlap, respecting sentence boundaries"""
    if len(text) <= max_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_size
        
        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence endings within the last 200 characters
            last_period = text.rfind('.', end - 200, end)
            last_newline = text.rfind('\n', end - 200, end)
            
            if last_period > start:
                end = last_period + 1
            elif last_newline > start:
                end = last_newline + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = max(start + max_size - overlap, end)
        
        if start >= len(text):
            break
    
    return chunks

class GTMFAzureLLMJudge:
    """Azure AI-based LLM judge for GTMF quality assessment"""
    
    def __init__(self, azure_client: AzureAIClient):
        self.azure_client = azure_client
    
    def judge_gtmf_quality(self, medical_text: str, gtmf: GTMF) -> GTMFJudgmentScore:
        """Comprehensive quality judgment using Azure AI"""
        logger.info("Starting Azure AI LLM judgment of GTMF quality")
        
        # Convert GTMF to dict for analysis
        gtmf_dict = gtmf.model_dump()
        
        # Prepare judgment prompt with shortened text to avoid token limits
        system_message = """You are an expert medical information extraction quality judge. Your task is to comprehensively evaluate the quality of medical information extraction results.

You will assess:
1. Completeness: How thoroughly was the medical information extracted?
2. Accuracy: Are the extracted items medically accurate and present in the original text?
3. Consistency: Is the extracted information internally consistent?
4. Medical Relevance: Are the extractions medically meaningful and appropriately categorized?
5. Structure: Is the output properly structured and formatted?

For each dimension, provide scores from 0-10 where:
- 0-3: Poor quality with major issues
- 4-6: Moderate quality with some issues
- 7-8: Good quality with minor issues
- 9-10: Excellent quality

Respond ONLY with valid JSON, no additional text or explanations."""
        
        # Limit text and extraction size for the prompt
        limited_text = medical_text[:800] + "..." if len(medical_text) > 800 else medical_text
        symptoms = [s.get('description', '') for s in gtmf_dict.get('Core_Fields', {}).get('Symptoms', [])][:5]
        diagnoses = [d.get('primary', '') for d in gtmf_dict.get('Core_Fields', {}).get('Diagnoses', [])][:5]
        treatments = [t.get('procedure', '') for t in gtmf_dict.get('Core_Fields', {}).get('Treatment_Options', [])][:5]
        
        user_message = f"""
        Evaluate this medical information extraction:

        ORIGINAL MEDICAL TEXT:
        {limited_text}

        EXTRACTED INFORMATION:
        Symptoms: {symptoms}
        Diagnoses: {diagnoses}
        Treatments: {treatments}

        Return assessment in this exact JSON format:
        {{
            "overall_score": 7.5,
            "completeness_score": 8.0,
            "accuracy_score": 7.0,
            "consistency_score": 8.5,
            "medical_relevance_score": 7.5,
            "structure_score": 9.0,
            "symptoms_quality": 7.0,
            "diagnoses_quality": 8.0,
            "treatments_quality": 6.5,
            "demographics_quality": 5.0,
            "confidence_level": 0.85,
            "strengths": ["accurate symptom extraction", "good structure"],
            "weaknesses": ["missed some treatments", "incomplete demographics"],
            "critical_issues": ["diagnosis accuracy needs review"],
            "recommendations": ["improve treatment extraction", "validate diagnoses"],
            "judgment_reasoning": "Overall good extraction with room for improvement in completeness."
        }}
        """
        
        try:
            response = self.azure_client.chat_completion(system_message, user_message, temperature=0.1)
            
            # Extract and parse JSON from response
            json_str = extract_valid_json(response, "object")
            judgment_data = safe_json_parse_object(json_str, "llm_judgment")
            
            if judgment_data and len(judgment_data) > 3:  # Basic validation
                return GTMFJudgmentScore(
                    overall_score=float(judgment_data.get('overall_score', 5.0)),
                    completeness_score=float(judgment_data.get('completeness_score', 5.0)),
                    accuracy_score=float(judgment_data.get('accuracy_score', 5.0)),
                    consistency_score=float(judgment_data.get('consistency_score', 5.0)),
                    medical_relevance_score=float(judgment_data.get('medical_relevance_score', 5.0)),
                    structure_score=float(judgment_data.get('structure_score', 5.0)),
                    symptoms_quality=float(judgment_data.get('symptoms_quality', 5.0)),
                    diagnoses_quality=float(judgment_data.get('diagnoses_quality', 5.0)),
                    treatments_quality=float(judgment_data.get('treatments_quality', 5.0)),
                    demographics_quality=float(judgment_data.get('demographics_quality', 5.0)),
                    confidence_level=float(judgment_data.get('confidence_level', 0.7)),
                    strengths=judgment_data.get('strengths', [])[:5],  # Limit list sizes
                    weaknesses=judgment_data.get('weaknesses', [])[:5],
                    critical_issues=judgment_data.get('critical_issues', [])[:5],
                    recommendations=judgment_data.get('recommendations', [])[:5],
                    judgment_reasoning=str(judgment_data.get('judgment_reasoning', 'Standard assessment completed.'))[:500]  # Limit length
                )
            else:
                logger.warning("Empty or insufficient judgment data from LLM judge")
                
        except Exception as e:
            logger.error(f"Azure AI LLM judgment failed: {e}")
        
        # Return default scores if judgment fails
        return GTMFJudgmentScore(
            overall_score=5.0, completeness_score=5.0, accuracy_score=5.0,
            consistency_score=5.0, medical_relevance_score=5.0, structure_score=5.0,
            symptoms_quality=5.0, diagnoses_quality=5.0, treatments_quality=5.0,
            demographics_quality=5.0, confidence_level=0.5,
            strengths=[], weaknesses=[], critical_issues=[], recommendations=[],
            judgment_reasoning="Judgment failed - using default scores"
        )
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 9.0:
            return "A+"
        elif score >= 8.5:
            return "A"
        elif score >= 8.0:
            return "A-"
        elif score >= 7.5:
            return "B+"
        elif score >= 7.0:
            return "B"
        elif score >= 6.5:
            return "B-"
        elif score >= 6.0:
            return "C+"
        elif score >= 5.5:
            return "C"
        elif score >= 5.0:
            return "C-"
        elif score >= 4.0:
            return "D"
        else:
            return "F"

def aggressive_json_clean(text: str) -> str:
    """Aggressively clean text to extract valid JSON"""
    # Remove all markdown
    text = re.sub(r'```[a-z]*\n?', '', text)
    text = re.sub(r'```', '', text)
    
    # Remove common prefixes
    prefixes = ['Here is the JSON:', 'JSON:', 'Response:', 'Output:', 'Result:']
    for prefix in prefixes:
        if text.strip().startswith(prefix):
            text = text.strip()[len(prefix):].strip()
    
    # Fix common JSON issues
    text = re.sub(r'\n+', ' ', text)  # Replace multiple newlines with space
    text = re.sub(r'\t+', ' ', text)  # Replace tabs with space
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    
    # Fix unescaped quotes in strings (common issue)
    text = re.sub(r'(?<!\\)"(?=\w)', '\\"', text)
    
    # Remove trailing commas
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    
    return text.strip()

def extract_valid_json(response: str, expected_type: str = "array") -> str:
    """Extract valid JSON from response with multiple strategies"""
    logger.debug(f"Extracting {expected_type} from response length: {len(response)}")
    
    # Clean the response
    cleaned = aggressive_json_clean(response)
    
    if expected_type == "array":
        # Find array boundaries
        start_char, end_char = '[', ']'
        start_idx = cleaned.find(start_char)
        if start_idx == -1:
            return "[]"
    else:  # object
        start_char, end_char = '{', '}'
        start_idx = cleaned.find(start_char)
        if start_idx == -1:
            return "{}"
    
    # Count brackets/braces to find matching closing
    count = 0
    end_idx = -1
    
    for i in range(start_idx, len(cleaned)):
        if cleaned[i] == start_char:
            count += 1
        elif cleaned[i] == end_char:
            count -= 1
            if count == 0:
                end_idx = i + 1
                break
    
    if end_idx > start_idx:
        candidate = cleaned[start_idx:end_idx]
        return candidate
    
    # Fallback: return empty structure
    return "[]" if expected_type == "array" else "{}"

def safe_json_parse_array(json_str: str, field_name: str = "") -> list:
    """Safely parse JSON array with fallback strategies"""
    if not json_str or json_str.strip() in ['', '[]']:
        return []
    
    logger.debug(f"Parsing array for {field_name}: {json_str[:100]}...")
    
    try:
        result = json.loads(json_str)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            # Sometimes the LLM wraps the array in an object
            for key, value in result.items():
                if isinstance(value, list):
                    return value
        return []
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error for {field_name}: {e}")
        
        # Try to fix and re-parse
        try:
            # Fix common issues
            cleaned = json_str.strip()
            
            # Ensure proper array formatting
            if not cleaned.startswith('['):
                cleaned = '[' + cleaned
            if not cleaned.endswith(']'):
                cleaned = cleaned + ']'
            
            # Try to fix quoted content
            cleaned = re.sub(r'(?<!\\)"(?=[^",\]\}]*")', '\\"', cleaned)
            
            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
                    
        except Exception as fix_error:
            logger.warning(f"Failed to fix JSON for {field_name}: {fix_error}")
        
        # Manual extraction as last resort
        try:
            return manual_extract_array_from_text(json_str, field_name)
        except Exception:
            logger.error(f"Manual extraction failed for {field_name}")
        
        # Return empty array if all parsing fails
        return []

def safe_json_parse_object(json_str: str, field_name: str = "") -> dict:
    """Safely parse JSON object with fallback strategies"""
    if not json_str or json_str.strip() in ['', '{}']:
        return {}
    
    logger.debug(f"Parsing object for {field_name}: {json_str[:100]}...")
    
    try:
        result = json.loads(json_str)
        if isinstance(result, dict):
            return result
        return {}
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error for {field_name}: {e}")
        
        # Try to fix and re-parse
        try:
            cleaned = json_str.strip()
            
            # Ensure proper object formatting
            if not cleaned.startswith('{'):
                cleaned = '{' + cleaned
            if not cleaned.endswith('}'):
                cleaned = cleaned + '}'
            
            # Fix common issues
            cleaned = re.sub(r'(?<!\\)"(?=[^",\]\}]*")', '\\"', cleaned)
            
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
                    
        except Exception as fix_error:
            logger.warning(f"Failed to fix JSON for {field_name}: {fix_error}")
        
        # Return empty object if all parsing fails
        return {}

def manual_extract_array_from_text(text: str, field_name: str) -> list:
    """Manually extract array data when JSON parsing fails"""
    logger.info(f"Attempting manual extraction for {field_name}")
    
    # Simple pattern matching based on field type
    if field_name == "symptoms":
        # Look for common symptom keywords
        symptoms = []
        text_lower = text.lower()
        symptom_keywords = ['pain', 'ache', 'fever', 'nausea', 'vomiting', 'fatigue', 'headache', 'dizziness']
        for keyword in symptom_keywords:
            if keyword in text_lower:
                symptoms.append(keyword)
        return symptoms
    
    elif field_name == "allergies" or field_name.endswith("medications"):
        # Look for drug names or common allergies
        items = []
        # Simple pattern: look for capitalized words that might be drug names
        words = re.findall(r'\b[A-Z][a-z]+\b', text)
        for word in words[:5]:  # Limit to first 5 to avoid noise
            if len(word) > 3:  # Avoid short words
                items.append(word)
        return items
    
    # Fallback: try to extract any quoted strings
    quoted_items = re.findall(r'"([^"]+)"', text)
    return quoted_items[:10]  # Limit to avoid noise

clean_json_response = aggressive_json_clean  # Alias for compatibility

class GTMFExtractionAgent:
    def __init__(self, endpoint: str = None, api_key: str = None, model_name: str = "gpt-4", 
                 include_llm_judge: bool = True, enable_chunking: bool = True):
        """
        Initialize GTMF Extraction Agent with Azure AI
        
        Args:
            endpoint: Azure AI endpoint URL
            api_key: Azure AI API key
            model_name: Model name to use
            include_llm_judge: Whether to enable LLM judge assessment
            enable_chunking: Whether to use text chunking for large documents
        """
        self.azure_client = AzureAIClient(endpoint, api_key, model_name, temperature=0.0)
        self.validator_client = AzureAIClient(endpoint, api_key, model_name, temperature=0.1, max_tokens=512)
        self.include_llm_judge = include_llm_judge
        self.enable_chunking = enable_chunking
        
        # Initialize LLM judge if requested
        self.llm_judge = None
        if include_llm_judge:
            try:
                self.llm_judge = GTMFAzureLLMJudge(self.azure_client)
                logger.info(f"GTMFAgent: Azure AI LLM Judge initialized with model {model_name}")
            except Exception as e:
                logger.warning(f"GTMFAgent: Failed to initialize LLM Judge: {e}. Continuing without LLM judgment.")
                self.include_llm_judge = False

    def extract_with_llm_judge(self, medical_text: str) -> Tuple[GTMF, dict]:
        """Extract GTMF with comprehensive quality assessment including LLM judge"""
        logger.info("GTMFAgent: Extracting GTMF with Azure AI LLM judge assessment...")
        
        # Perform standard extraction with quality metrics
        gtmf, quality_assessment = self.extract_with_quality_assessment(medical_text)
        
        # Add LLM judge assessment if enabled
        if self.include_llm_judge and self.llm_judge:
            try:
                logger.info("GTMFAgent: Running Azure AI LLM judge assessment...")
                llm_judgment = self.llm_judge.judge_gtmf_quality(medical_text, gtmf)
                
                # Integrate LLM judgment into quality assessment
                quality_assessment["llm_judgment"] = {
                    "enabled": True,
                    "overall_score": llm_judgment.overall_score,
                    "dimensional_scores": {
                        "completeness": llm_judgment.completeness_score,
                        "accuracy": llm_judgment.accuracy_score,
                        "consistency": llm_judgment.consistency_score,
                        "medical_relevance": llm_judgment.medical_relevance_score,
                        "structure": llm_judgment.structure_score
                    },
                    "field_scores": {
                        "symptoms": llm_judgment.symptoms_quality,
                        "diagnoses": llm_judgment.diagnoses_quality,
                        "treatments": llm_judgment.treatments_quality,
                        "demographics": llm_judgment.demographics_quality
                    },
                    "confidence_level": llm_judgment.confidence_level,
                    "strengths": llm_judgment.strengths,
                    "weaknesses": llm_judgment.weaknesses,
                    "critical_issues": llm_judgment.critical_issues,
                    "recommendations": llm_judgment.recommendations,
                    "judgment_reasoning": llm_judgment.judgment_reasoning,
                    "grade": self.llm_judge._score_to_grade(llm_judgment.overall_score)
                }
                
                # Update overall confidence based on LLM judgment
                if llm_judgment.confidence_level > 0.7:  # High confidence LLM judgment
                    # Weight LLM assessment with rule-based assessment
                    original_confidence = quality_assessment["overall_confidence"]
                    llm_confidence = llm_judgment.overall_score / 10.0  # Convert to 0-1 scale
                    
                    # Weighted average (60% LLM, 40% rule-based)
                    quality_assessment["overall_confidence"] = (
                        original_confidence * 0.4 + llm_confidence * 0.6
                    )
                    
                    # Add LLM insights to recommendations
                    quality_assessment["recommendations"].extend(llm_judgment.recommendations)
                
                logger.info(f"GTMFAgent: Azure AI LLM judge completed. Score: {llm_judgment.overall_score:.1f}/10, "
                           f"Confidence: {llm_judgment.confidence_level:.2f}")
                
            except Exception as e:
                logger.error(f"GTMFAgent: Azure AI LLM judge assessment failed: {e}")
                quality_assessment["llm_judgment"] = {
                    "enabled": True,
                    "error": str(e),
                    "status": "failed"
                }
        else:
            quality_assessment["llm_judgment"] = {
                "enabled": False,
                "status": "disabled"
            }
        
        logger.info("GTMFAgent: Enhanced extraction with Azure AI LLM judge completed")
        return gtmf, quality_assessment

    def extract_with_quality_assessment(self, medical_text: str) -> Tuple[GTMF, dict]:
        """Extract GTMF with comprehensive quality assessment using chunking if enabled"""
        logger.info("Extracting GTMF with quality assessment...")
        
        if self.enable_chunking and len(medical_text) > 2500:
            return self._extract_with_chunking(medical_text)
        else:
            return self._extract_single_pass(medical_text)

    def _extract_with_chunking(self, medical_text: str) -> Tuple[GTMF, dict]:
        """Extract GTMF using chunking strategy"""
        logger.info("Using chunking strategy for large medical text")
        
        # Chunk the text
        chunks = chunk_medical_text(medical_text, max_chunk_size=2500, overlap=150)
        logger.info(f"Processing {len(chunks)} chunks")
        
        # Extract from each chunk
        chunk_extractions = []
        for i, chunk_info in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} - Section: {chunk_info['section']}")
            
            try:
                chunk_gtmf, _ = self._extract_single_pass(chunk_info['content'])
                chunk_extractions.append(chunk_gtmf.model_dump())
            except Exception as e:
                logger.error(f"Error processing chunk {i+1}: {e}")
                continue
        
        # Merge chunk extractions
        merged_extraction = self._merge_chunk_extractions(chunk_extractions)
        gtmf = GTMF(**merged_extraction)
        
        # Calculate quality assessment for merged result
        quality_assessment = self._assess_merged_extraction_quality(medical_text, gtmf, chunks)
        
        return gtmf, quality_assessment

    def _extract_single_pass(self, medical_text: str) -> Tuple[GTMF, dict]:
        """Extract GTMF in single pass without chunking"""
        # Extract individual components with quality metrics
        symptoms, symptoms_metrics = self._extract_symptoms_with_quality(medical_text)
        diagnoses, diagnoses_metrics = self._extract_diagnoses_with_quality(medical_text)
        treatments, treatments_metrics = self._extract_treatments_with_quality(medical_text)
        history, history_metrics = self._extract_history_with_quality(medical_text)
        allergies, allergies_metrics = self._extract_allergies_with_quality(medical_text)
        
        # Extract medications
        current_medications, current_meds_metrics = self._extract_medications_with_quality(medical_text, "current")
        discharge_medications, discharge_meds_metrics = self._extract_medications_with_quality(medical_text, "discharge")
        
        # Patient demographics (usually provided separately)
        patient_demographics = PatientDemographics(
            Date_of_Birth="not provided", Age=0, Sex="not provided", Religion="not provided",
            Marital_Status="not provided", Ethnicity="not provided", Insurance="not provided",
            Admission_Type="not provided", Admission_Date="not provided", Discharge_Date="not provided"
        )

        # Construct GTMF
        core = CoreFields(Symptoms=symptoms, Diagnoses=diagnoses, Treatment_Options=treatments)
        context = ContextFields(
            Patient_Demographics=patient_demographics,
            Medical_History=history if history else MedicalHistory(Past_Medical_History="not provided"),
            Allergies=allergies or [],
            Current_Medications=current_medications,
            Discharge_Medications=discharge_medications
        )
        additional = AdditionalContext(Chief_Complaint="not provided")

        gtmf = GTMF(Core_Fields=core, Context_Fields=context, Additional_Context=additional)
        
        # Compile quality assessment
        quality_assessment = {
            "overall_confidence": self._calculate_overall_confidence([
                symptoms_metrics, diagnoses_metrics, treatments_metrics, 
                history_metrics, allergies_metrics, current_meds_metrics, discharge_meds_metrics
            ]),
            "field_quality": {
                "symptoms": symptoms_metrics.__dict__,
                "diagnoses": diagnoses_metrics.__dict__,
                "treatments": treatments_metrics.__dict__,
                "history": history_metrics.__dict__,
                "allergies": allergies_metrics.__dict__,
                "current_medications": current_meds_metrics.__dict__,
                "discharge_medications": discharge_meds_metrics.__dict__
            },
            "extraction_completeness": self._assess_extraction_completeness(medical_text, gtmf),
            "medical_consistency": self._assess_medical_consistency(gtmf),
            "recommendations": self._generate_improvement_recommendations([
                symptoms_metrics, diagnoses_metrics, treatments_metrics, 
                history_metrics, allergies_metrics, current_meds_metrics, discharge_meds_metrics
            ])
        }
        
        logger.info(f"GTMF extraction complete with overall confidence: {quality_assessment['overall_confidence']:.2f}")
        return gtmf, quality_assessment

    def extract(self, medical_text: str, use_llm_judge: bool = None) -> GTMF:
        """
        Extract GTMF from medical text
        
        Args:
            medical_text: The medical text to extract from
            use_llm_judge: Whether to use LLM judge (None uses instance setting)
        
        Returns:
            GTMF: The extracted GTMF instance
        """
        if use_llm_judge is None:
            use_llm_judge = self.include_llm_judge
        
        if use_llm_judge and self.llm_judge:
            gtmf, _ = self.extract_with_llm_judge(medical_text)
        else:
            gtmf, _ = self.extract_with_quality_assessment(medical_text)
        
        return gtmf

    def _extract_symptoms_with_quality(self, note_text: str) -> Tuple[list, ExtractionQualityMetrics]:
        """Extract symptoms with quality assessment using Azure AI"""
        system_message = """You are a medical symptom extraction specialist. Extract all symptoms mentioned in the medical text. 
        
        Focus on:
        - Patient-reported symptoms
        - Clinical observations of symptoms
        - Signs and symptoms from examination
        
        Return symptoms as a JSON array of objects with 'description' field. Respond ONLY with the JSON array, no additional text."""
        
        user_message = f"""
        Extract all symptoms from this medical text:
        
        {note_text}
        
        Return as JSON array:
        [
            {{"description": "symptom description"}},
            {{"description": "another symptom"}}
        ]
        
        If no symptoms found, return empty array: []
        """
        
        try:
            response = self.azure_client.chat_completion(system_message, user_message)
            json_str = clean_json_response(response)
            symptoms_data = safe_json_parse_array(json_str, "symptoms")
            
            # Convert to required format
            symptoms = []
            for symptom_data in symptoms_data:
                if isinstance(symptom_data, dict) and 'description' in symptom_data:
                    # Create symptom object with required structure
                    symptom = type('Symptom', (), {
                        'description': symptom_data['description'],
                        'severity': 'not provided',
                        'duration': 'not provided',
                        'location': 'not provided'
                    })()
                    symptoms.append(symptom)
                elif isinstance(symptom_data, str):
                    # Handle case where just strings are returned
                    symptom = type('Symptom', (), {
                        'description': symptom_data,
                        'severity': 'not provided',
                        'duration': 'not provided',
                        'location': 'not provided'
                    })()
                    symptoms.append(symptom)
                    
        except Exception as e:
            logger.error(f"Error extracting symptoms: {e}")
            symptoms = []
        
        # Assess quality
        confidence = self._assess_symptom_extraction_confidence(note_text, symptoms)
        coverage = self._assess_text_coverage(note_text, symptoms, "symptom")
        validation = self._validate_medical_terms([s.description for s in symptoms], "symptoms")
        completeness = self._assess_field_completeness(symptoms)
        
        metrics = ExtractionQualityMetrics(
            extraction_confidence=confidence,
            text_coverage=coverage,
            validation_score=validation,
            completeness=completeness
        )
        
        return symptoms, metrics

    def _extract_diagnoses_with_quality(self, note_text: str) -> Tuple[list, ExtractionQualityMetrics]:
        """Extract diagnoses with quality assessment using Azure AI"""
        system_message = """You are a medical diagnosis extraction specialist. Extract all diagnoses mentioned in the medical text.
        
        Focus on:
        - Primary diagnoses
        - Secondary diagnoses
        - Working diagnoses
        - Differential diagnoses
        
        Return diagnoses as objects with 'primary' field. Respond ONLY with the JSON array, no additional text."""
        
        user_message = f"""
        Extract all diagnoses from this medical text:
        
        {note_text}
        
        Return as JSON array:
        [
            {{"primary": "diagnosis name"}},
            {{"primary": "another diagnosis"}}
        ]
        
        If no diagnoses found, return empty array: []
        """
        
        try:
            response = self.azure_client.chat_completion(system_message, user_message)
            json_str = clean_json_response(response)
            diagnoses_data = safe_json_parse_array(json_str, "diagnoses")
            
            # Convert to required format
            diagnoses = []
            for diagnosis_data in diagnoses_data:
                if isinstance(diagnosis_data, dict) and 'primary' in diagnosis_data:
                    # Create diagnosis object with required structure
                    diagnosis = type('Diagnosis', (), {
                        'primary': diagnosis_data['primary'],
                        'secondary': 'not provided',
                        'icd_code': 'not provided'
                    })()
                    diagnoses.append(diagnosis)
                elif isinstance(diagnosis_data, str):
                    # Handle case where just strings are returned
                    diagnosis = type('Diagnosis', (), {
                        'primary': diagnosis_data,
                        'secondary': 'not provided',
                        'icd_code': 'not provided'
                    })()
                    diagnoses.append(diagnosis)
                    
        except Exception as e:
            logger.error(f"Error extracting diagnoses: {e}")
            diagnoses = []
        
        confidence = self._assess_diagnosis_extraction_confidence(note_text, diagnoses)
        coverage = self._assess_text_coverage(note_text, diagnoses, "diagnosis")
        validation = self._validate_medical_terms([d.primary for d in diagnoses], "diagnoses")
        completeness = self._assess_field_completeness(diagnoses)
        
        metrics = ExtractionQualityMetrics(
            extraction_confidence=confidence,
            text_coverage=coverage,
            validation_score=validation,
            completeness=completeness
        )
        
        return diagnoses, metrics

    def _extract_treatments_with_quality(self, note_text: str) -> Tuple[list, ExtractionQualityMetrics]:
        """Extract treatments with quality assessment using Azure AI"""
        system_message = """You are a medical treatment extraction specialist. Extract all treatments, procedures, and interventions mentioned in the medical text.
        
        Focus on:
        - Medications and dosages
        - Surgical procedures
        - Therapeutic interventions
        - Treatment plans
        
        Return treatments as objects with 'procedure' field. Respond ONLY with the JSON array, no additional text."""
        
        user_message = f"""
        Extract all treatments from this medical text:
        
        {note_text}
        
        Return as JSON array:
        [
            {{"procedure": "treatment/procedure name"}},
            {{"procedure": "another treatment"}}
        ]
        
        If no treatments found, return empty array: []
        """
        
        try:
            response = self.azure_client.chat_completion(system_message, user_message)
            json_str = clean_json_response(response)
            treatments_data = safe_json_parse_array(json_str, "treatments")
            
            # Convert to required format
            treatments = []
            for treatment_data in treatments_data:
                if isinstance(treatment_data, dict) and 'procedure' in treatment_data:
                    # Create treatment object with required structure
                    treatment = type('Treatment', (), {
                        'procedure': treatment_data['procedure'],
                        'dosage': 'not provided',
                        'frequency': 'not provided',
                        'duration': 'not provided'
                    })()
                    treatments.append(treatment)
                elif isinstance(treatment_data, str):
                    # Handle case where just strings are returned
                    treatment = type('Treatment', (), {
                        'procedure': treatment_data,
                        'dosage': 'not provided',
                        'frequency': 'not provided',
                        'duration': 'not provided'
                    })()
                    treatments.append(treatment)
                    
        except Exception as e:
            logger.error(f"Error extracting treatments: {e}")
            treatments = []
        
        confidence = self._assess_treatment_extraction_confidence(note_text, treatments)
        coverage = self._assess_text_coverage(note_text, treatments, "treatment")
        validation = self._validate_medical_terms([t.procedure for t in treatments], "treatments")
        completeness = self._assess_field_completeness(treatments)
        
        metrics = ExtractionQualityMetrics(
            extraction_confidence=confidence,
            text_coverage=coverage,
            validation_score=validation,
            completeness=completeness
        )
        
        return treatments, metrics

    def _extract_history_with_quality(self, note_text: str) -> Tuple[object, ExtractionQualityMetrics]:
        """Extract medical history with quality assessment using Azure AI"""
        system_message = """You are a medical history extraction specialist. Extract past medical history information from the medical text. Respond ONLY with JSON object, no additional text."""
        
        user_message = f"""
        Extract past medical history from this medical text:
        
        {note_text}
        
        Return as JSON object:
        {{"Past_Medical_History": "relevant past medical history or 'not provided' if none found"}}
        """
        
        try:
            response = self.azure_client.chat_completion(system_message, user_message)
            json_str = clean_json_response(response)
            history_data = safe_json_parse_object(json_str, "history")
            
            history = MedicalHistory(
                Past_Medical_History=history_data.get('Past_Medical_History', 'not provided')
            )
                
        except Exception as e:
            logger.error(f"Error extracting history: {e}")
            history = MedicalHistory(Past_Medical_History='not provided')
        
        confidence = 0.8 if history and history.Past_Medical_History != "not provided" else 0.2
        coverage = 0.7 if "history" in note_text.lower() else 0.3
        validation = 0.8  # History is typically free text, harder to validate
        completeness = 1.0 if history else 0.0
        
        metrics = ExtractionQualityMetrics(
            extraction_confidence=confidence,
            text_coverage=coverage,
            validation_score=validation,
            completeness=completeness
        )
        
        return history, metrics

    def _extract_allergies_with_quality(self, note_text: str) -> Tuple[list, ExtractionQualityMetrics]:
        """Extract allergies with quality assessment using Azure AI"""
        system_message = """You are an allergy extraction specialist. Extract all allergies mentioned in the medical text. Respond ONLY with JSON array, no additional text."""
        
        user_message = f"""
        Extract all allergies from this medical text:
        
        {note_text}
        
        Return as JSON array of strings:
        ["allergy1", "allergy2", ...]
        
        If no allergies found or "NKDA" (no known drug allergies), return empty array: []
        """
        
        try:
            response = self.azure_client.chat_completion(system_message, user_message)
            json_str = clean_json_response(response)
            allergies = safe_json_parse_array(json_str, "allergies")
            
            # Ensure it's a list of strings
            if not isinstance(allergies, list):
                allergies = []
            else:
                allergies = [str(allergy) for allergy in allergies if str(allergy).strip()]
                
        except Exception as e:
            logger.error(f"Error extracting allergies: {e}")
            allergies = []
        
        confidence = 0.9 if allergies else 0.7  # High confidence in allergy extraction
        coverage = 0.8 if "allerg" in note_text.lower() else 0.5
        validation = 0.9  # Allergies are usually straightforward
        completeness = 1.0 if allergies else 0.8  # May legitimately be empty
        
        metrics = ExtractionQualityMetrics(
            extraction_confidence=confidence,
            text_coverage=coverage,
            validation_score=validation,
            completeness=completeness
        )
        
        return allergies, metrics

    def _extract_medications_with_quality(self, note_text: str, med_type: str) -> Tuple[list, ExtractionQualityMetrics]:
        """Extract medications with quality assessment using Azure AI"""
        system_message = f"""You are a medication extraction specialist. Extract {med_type} medications mentioned in the medical text. Respond ONLY with JSON array, no additional text."""
        
        user_message = f"""
        Extract {med_type} medications from this medical text:
        
        {note_text}
        
        Return as JSON array of strings:
        ["medication1", "medication2", ...]
        
        If no {med_type} medications found, return empty array: []
        """
        
        try:
            response = self.azure_client.chat_completion(system_message, user_message)
            json_str = clean_json_response(response)
            medications = safe_json_parse_array(json_str, f"{med_type}_medications")
            
            # Ensure it's a list of strings
            if not isinstance(medications, list):
                medications = []
            else:
                medications = [str(med) for med in medications if str(med).strip()]
                
        except Exception as e:
            logger.error(f"Error extracting {med_type} medications: {e}")
            medications = []
        
        confidence = 0.8 if medications else 0.6
        coverage = 0.7 if "medication" in note_text.lower() or "drug" in note_text.lower() else 0.4
        validation = self._validate_medical_terms(medications, "medications")
        completeness = 1.0 if medications else 0.7  # May legitimately be empty
        
        metrics = ExtractionQualityMetrics(
            extraction_confidence=confidence,
            text_coverage=coverage,
            validation_score=validation,
            completeness=completeness
        )
        
        return medications, metrics

    def _merge_chunk_extractions(self, extractions: List[Dict]) -> Dict:
        """Merge extractions from multiple chunks"""
        if not extractions:
            # Return empty GTMF structure
            return {
                "Core_Fields": {
                    "Symptoms": [],
                    "Diagnoses": [],
                    "Treatment_Options": []
                },
                "Context_Fields": {
                    "Patient_Demographics": {
                        "Date_of_Birth": "not provided",
                        "Age": 0,
                        "Sex": "not provided",
                        "Religion": "not provided",
                        "Marital_Status": "not provided",
                        "Ethnicity": "not provided",
                        "Insurance": "not provided",
                        "Admission_Type": "not provided",
                        "Admission_Date": "not provided",
                        "Discharge_Date": "not provided"
                    },
                    "Medical_History": {"Past_Medical_History": "not provided"},
                    "Allergies": [],
                    "Current_Medications": [],
                    "Discharge_Medications": []
                },
                "Additional_Context": {"Chief_Complaint": "not provided"}
            }
        
        if len(extractions) == 1:
            return extractions[0]
        
        # Start with the first extraction as base
        merged = extractions[0].copy()
        
        # Merge core fields
        merged_symptoms = []
        merged_diagnoses = []
        merged_treatments = []
        
        seen_symptoms = set()
        seen_diagnoses = set()
        seen_treatments = set()
        
        for extraction in extractions:
            core_fields = extraction.get("Core_Fields", {})
            
            # Merge symptoms
            for symptom in core_fields.get("Symptoms", []):
                desc = symptom.get("description", "").strip().lower()
                if desc and desc != "not provided" and desc not in seen_symptoms:
                    merged_symptoms.append(symptom)
                    seen_symptoms.add(desc)
            
            # Merge diagnoses
            for diagnosis in core_fields.get("Diagnoses", []):
                primary = diagnosis.get("primary", "").strip().lower()
                if primary and primary != "not provided" and primary not in seen_diagnoses:
                    merged_diagnoses.append(diagnosis)
                    seen_diagnoses.add(primary)
            
            # Merge treatments
            for treatment in core_fields.get("Treatment_Options", []):
                procedure = treatment.get("procedure", "").strip().lower()
                if procedure and procedure != "not provided" and procedure not in seen_treatments:
                    merged_treatments.append(treatment)
                    seen_treatments.add(procedure)
        
        # Update merged extraction
        merged["Core_Fields"]["Symptoms"] = merged_symptoms
        merged["Core_Fields"]["Diagnoses"] = merged_diagnoses
        merged["Core_Fields"]["Treatment_Options"] = merged_treatments
        
        return merged

    def _assess_merged_extraction_quality(self, original_text: str, gtmf: GTMF, chunks: List[Dict]) -> Dict:
        """Assess quality of merged extraction from chunks"""
        # Calculate basic quality metrics
        chunk_count = len(chunks)
        text_length = len(original_text)
        
        # Count extracted items
        symptom_count = len([s for s in gtmf.Core_Fields.Symptoms if s.description != "not provided"])
        diagnosis_count = len([d for d in gtmf.Core_Fields.Diagnoses if d.primary != "not provided"])
        treatment_count = len([t for t in gtmf.Core_Fields.Treatment_Options if t.procedure != "not provided"])
        
        # Estimate completeness based on text length and chunking
        expected_items = max(1, text_length // 300)  # Rough heuristic
        actual_items = symptom_count + diagnosis_count + treatment_count
        completeness = min(1.0, actual_items / expected_items)
        
        # Chunking quality bonus (better processing of large texts)
        chunking_bonus = min(0.1, chunk_count * 0.02)
        
        quality_assessment = {
            "overall_confidence": min(1.0, completeness + chunking_bonus),
            "field_quality": {
                "symptoms": {"extraction_confidence": 0.8 if symptom_count > 0 else 0.5},
                "diagnoses": {"extraction_confidence": 0.8 if diagnosis_count > 0 else 0.5},
                "treatments": {"extraction_confidence": 0.8 if treatment_count > 0 else 0.5},
            },
            "extraction_completeness": completeness,
            "medical_consistency": 0.8,  # Assume good consistency from chunked extraction
            "chunking_info": {
                "chunk_count": chunk_count,
                "strategy": "section-aware",
                "overlap_size": 150
            },
            "recommendations": []
        }
        
        return quality_assessment

    # Helper methods remain largely the same but adapted for Azure AI...
    def _assess_symptom_extraction_confidence(self, text: str, symptoms: list) -> float:
        """Assess confidence in symptom extraction"""
        if not symptoms:
            # Check if symptoms should have been found
            symptom_indicators = ["pain", "ache", "discomfort", "nausea", "fever", "cough"]
            if any(indicator in text.lower() for indicator in symptom_indicators):
                return 0.2  # Low confidence - missed symptoms
            return 0.8  # Good confidence - no symptoms to find
        
        # Check if extracted symptoms are mentioned in text
        found_in_text = 0
        for symptom in symptoms:
            desc = symptom.description.lower()
            if desc in text.lower() or any(word in text.lower() for word in desc.split() if len(word) > 3):
                found_in_text += 1
        
        return found_in_text / len(symptoms) if symptoms else 1.0

    def _assess_diagnosis_extraction_confidence(self, text: str, diagnoses: list) -> float:
        """Assess confidence in diagnosis extraction"""
        if not diagnoses:
            diagnostic_keywords = ["diagnosis", "diagnosed with", "condition", "disease"]
            if any(keyword in text.lower() for keyword in diagnostic_keywords):
                return 0.3  # Missed diagnoses
            return 0.8  # No diagnoses to find
        
        # Validate diagnoses against text
        found_in_text = 0
        for diagnosis in diagnoses:
            primary = diagnosis.primary.lower()
            if primary in text.lower() or any(word in text.lower() for word in primary.split() if len(word) > 3):
                found_in_text += 1
        
        return found_in_text / len(diagnoses) if diagnoses else 1.0

    def _assess_treatment_extraction_confidence(self, text: str, treatments: list) -> float:
        """Assess confidence in treatment extraction"""
        if not treatments:
            treatment_keywords = ["treatment", "therapy", "medication", "prescribed"]
            if any(keyword in text.lower() for keyword in treatment_keywords):
                return 0.3
            return 0.8
        
        found_in_text = 0
        for treatment in treatments:
            procedure = treatment.procedure.lower()
            if procedure in text.lower() or any(word in text.lower() for word in procedure.split() if len(word) > 3):
                found_in_text += 1
        
        return found_in_text / len(treatments) if treatments else 1.0

    def _assess_text_coverage(self, text: str, extracted_items: list, item_type: str) -> float:
        """Assess how well the extraction covers the relevant text content"""
        if not extracted_items:
            return 0.5  # Neutral score for empty extractions
        
        # Simple heuristic: count of relevant words captured
        relevant_words = self._get_relevant_words_for_type(text, item_type)
        if not relevant_words:
            return 1.0
        
        captured_words = set()
        for item in extracted_items:
            if hasattr(item, 'description'):
                captured_words.update(item.description.lower().split())
            elif hasattr(item, 'primary'):
                captured_words.update(item.primary.lower().split())
            elif hasattr(item, 'procedure'):
                captured_words.update(item.procedure.lower().split())
        
        overlap = len(relevant_words.intersection(captured_words))
        return min(1.0, overlap / len(relevant_words))

    def _get_relevant_words_for_type(self, text: str, item_type: str) -> set:
        """Extract relevant words from text based on item type"""
        text_lower = text.lower()
        
        if item_type == "symptom":
            section_text = self._extract_section_text(text_lower, ["chief complaint", "history of present", "symptoms"])
        elif item_type == "diagnosis":
            section_text = self._extract_section_text(text_lower, ["diagnosis", "assessment", "impression"])
        elif item_type == "treatment":
            section_text = self._extract_section_text(text_lower, ["treatment", "plan", "medications", "therapy"])
        else:
            section_text = text_lower
        
        # Remove common stop words and extract meaningful terms
        words = set(re.findall(r'\b[a-zA-Z]{3,}\b', section_text))
        stop_words = {'the', 'and', 'was', 'for', 'are', 'with', 'his', 'her', 'this', 'that', 'from', 'they', 'been', 'have', 'were', 'said', 'each', 'which'}
        return words - stop_words

    def _extract_section_text(self, text: str, section_indicators: list) -> str:
        """Extract text from specific sections of the medical note"""
        for indicator in section_indicators:
            start_idx = text.find(indicator)
            if start_idx != -1:
                # Find next section or end of text
                next_section_idx = len(text)
                for next_indicator in ["assessment", "plan", "discharge", "follow"]:
                    if next_indicator != indicator:
                        next_idx = text.find(next_indicator, start_idx + len(indicator))
                        if next_idx != -1 and next_idx < next_section_idx:
                            next_section_idx = next_idx
                
                return text[start_idx:next_section_idx]
        
        return text  # Return full text if no specific section found

    def _validate_medical_terms(self, terms: list, term_type: str) -> float:
        """Validate extracted medical terms using Azure AI"""
        if not terms or all(term == "not provided" for term in terms):
            return 1.0  # No terms to validate
        
        # Simple validation prompt
        system_message = f"""You are a medical terminology validator. Assess the medical accuracy and appropriateness of {term_type}."""
        
        user_message = f"""
        Validate these medical {term_type}: {', '.join(terms[:5])}  # Limit for prompt size
        
        Rate from 0.0 to 1.0 how medically accurate and properly formatted these terms are.
        Consider: Are they real medical terms? Are they appropriately specific? 
        Respond with just a number between 0.0 and 1.0.
        """
        
        try:
            response_text = self.validator_client.chat_completion(system_message, user_message)
            
            # Extract score
            score_match = re.search(r'0\.\d+|1\.0|0\.0', response_text)
            if score_match:
                return float(score_match.group())
        except Exception as e:
            logger.warning(f"Azure AI medical term validation failed: {e}")
        
        return 0.7  # Default moderate score

    def _assess_field_completeness(self, field_items: list) -> float:
        """Assess completeness of extracted field items"""
        if not field_items:
            return 0.0
        
        complete_items = 0
        for item in field_items:
            if hasattr(item, 'description') and item.description and item.description != "not provided":
                complete_items += 1
            elif hasattr(item, 'primary') and item.primary and item.primary != "not provided":
                complete_items += 1
            elif hasattr(item, 'procedure') and item.procedure and item.procedure != "not provided":
                complete_items += 1
            elif isinstance(item, str) and item.strip():
                complete_items += 1
        
        return complete_items / len(field_items)

    def _calculate_overall_confidence(self, metrics_list: list) -> float:
        """Calculate overall confidence from individual field metrics"""
        if not metrics_list:
            return 0.0
        
        total_confidence = sum(m.extraction_confidence for m in metrics_list)
        total_validation = sum(m.validation_score for m in metrics_list)
        total_completeness = sum(m.completeness for m in metrics_list)
        
        # Weighted average
        overall = (total_confidence * 0.4 + total_validation * 0.3 + total_completeness * 0.3) / len(metrics_list)
        return round(overall, 3)

    def _assess_extraction_completeness(self, text: str, gtmf: GTMF) -> float:
        """Assess how completely the GTMF captures the medical text"""
        text_length = len(text.split())
        
        # Count non-empty extractions
        symptom_count = len([s for s in gtmf.Core_Fields.Symptoms if s.description != "not provided"])
        diagnosis_count = len([d for d in gtmf.Core_Fields.Diagnoses if d.primary != "not provided"])
        treatment_count = len([t for t in gtmf.Core_Fields.Treatment_Options if t.procedure != "not provided"])
        
        # Heuristic: expect roughly 1 item per 100-200 words
        expected_total = max(1, text_length // 150)
        actual_total = symptom_count + diagnosis_count + treatment_count
        
        completeness = min(1.0, actual_total / expected_total)
        return round(completeness, 3)

    def _assess_medical_consistency(self, gtmf: GTMF) -> float:
        """Assess internal medical consistency of the GTMF"""
        # Simple consistency checks
        symptoms = [s.description.lower() for s in gtmf.Core_Fields.Symptoms if s.description != "not provided"]
        diagnoses = [d.primary.lower() for d in gtmf.Core_Fields.Diagnoses if d.primary != "not provided"]
        
        if not symptoms or not diagnoses:
            return 0.8  # Neutral score if missing data
        
        # Check for basic keyword overlap between symptoms and diagnoses
        symptom_words = set()
        for symptom in symptoms:
            symptom_words.update(symptom.split())
        
        diagnosis_words = set()
        for diagnosis in diagnoses:
            diagnosis_words.update(diagnosis.split())
        
        # Calculate overlap
        if symptom_words and diagnosis_words:
            overlap = len(symptom_words.intersection(diagnosis_words))
            total_unique = len(symptom_words.union(diagnosis_words))
            consistency = overlap / total_unique if total_unique > 0 else 0.0
        else:
            consistency = 0.5
        
        return round(min(1.0, consistency + 0.5), 3)  # Boost base score since perfect overlap isn't expected

    def _generate_improvement_recommendations(self, metrics_list: list) -> list:
        """Generate specific recommendations for improving extraction quality"""
        recommendations = []
        
        # Check individual field quality
        if len(metrics_list) > 0 and metrics_list[0].extraction_confidence < 0.7:
            recommendations.append("Improve symptom extraction: enhance pattern matching for symptom descriptions")
        
        if len(metrics_list) > 1 and metrics_list[1].validation_score < 0.7:
            recommendations.append("Validate diagnosis terminology: ensure extracted diagnoses are medically accurate")
        
        if len(metrics_list) > 2 and metrics_list[2].text_coverage < 0.6:
            recommendations.append("Enhance treatment extraction: capture more treatment modalities from text")
        
        # Overall recommendations
        if metrics_list:
            avg_confidence = sum(m.extraction_confidence for m in metrics_list) / len(metrics_list)
            
            if avg_confidence < 0.6:
                recommendations.append("Overall extraction confidence is low: consider model fine-tuning or prompt optimization")
        
        return recommendations

    def extract_with_detailed_report(self, medical_text: str) -> Tuple[GTMF, dict, str]:
        """
        Extract GTMF with comprehensive quality assessment and human-readable report
        
        Args:
            medical_text: The medical text to extract from
            
        Returns:
            Tuple[GTMF, dict, str]: GTMF instance, quality assessment dict, and human-readable report
        """
        gtmf, quality_assessment = self.extract_with_llm_judge(medical_text)
        
        # Generate human-readable report
        report_lines = [
            "🏥 GTMF AZURE AI EXTRACTION QUALITY REPORT",
            "=" * 55,
            f"Overall Confidence: {quality_assessment['overall_confidence']:.3f}",
            ""
        ]
        
        # Field quality scores
        if "field_quality" in quality_assessment:
            field_quality = quality_assessment["field_quality"]
            report_lines.extend([
                "📊 Field Quality Scores:",
                f"├─ Symptoms: {field_quality.get('symptoms', {}).get('extraction_confidence', 0):.3f}",
                f"├─ Diagnoses: {field_quality.get('diagnoses', {}).get('extraction_confidence', 0):.3f}",
                f"├─ Treatments: {field_quality.get('treatments', {}).get('extraction_confidence', 0):.3f}",
                f"└─ History: {field_quality.get('history', {}).get('extraction_confidence', 0):.3f}",
                ""
            ])
        
        # Chunking information
        if "chunking_info" in quality_assessment:
            chunking_info = quality_assessment["chunking_info"]
            report_lines.extend([
                "📄 Chunking Information:",
                f"├─ Chunks Processed: {chunking_info['chunk_count']}",
                f"├─ Strategy: {chunking_info['strategy']}",
                f"└─ Overlap Size: {chunking_info['overlap_size']} chars",
                ""
            ])
        
        # Azure AI LLM Judge results
        if quality_assessment.get("llm_judgment", {}).get("enabled"):
            llm_judgment = quality_assessment["llm_judgment"]
            if "error" not in llm_judgment:
                report_lines.extend([
                    "🤖 Azure AI LLM Judge Assessment:",
                    f"├─ Overall Score: {llm_judgment['overall_score']:.1f}/10",
                    f"├─ Grade: {llm_judgment['grade']}",
                    f"├─ Confidence: {llm_judgment['confidence_level']:.1%}",
                    f"└─ Medical Relevance: {llm_judgment['dimensional_scores']['medical_relevance']:.1f}/10",
                    ""
                ])
                
                if llm_judgment.get('strengths'):
                    report_lines.extend([
                        "✅ Strengths:",
                        *[f"• {strength}" for strength in llm_judgment['strengths'][:3]],
                        ""
                    ])
                
                if llm_judgment.get('critical_issues'):
                    report_lines.extend([
                        "🚨 Critical Issues:",
                        *[f"• {issue}" for issue in llm_judgment['critical_issues'][:3]],
                        ""
                    ])
                
                if llm_judgment.get('recommendations'):
                    report_lines.extend([
                        "💡 Azure AI Recommendations:",
                        *[f"• {rec}" for rec in llm_judgment['recommendations'][:3]],
                        ""
                    ])
            else:
                report_lines.extend([
                    "❌ Azure AI LLM Judge Assessment Failed:",
                    f"Error: {llm_judgment['error']}",
                    ""
                ])
        
        # General recommendations
        if quality_assessment.get("recommendations"):
            report_lines.extend([
                "📋 General Recommendations:",
                *[f"• {rec}" for rec in quality_assessment["recommendations"][:3]]
            ])
        
        human_readable_report = "\n".join(report_lines)

        return gtmf, quality_assessment, human_readable_report

    def extract_batch(self, ehr_cases: List[Dict], use_llm_judge: bool = None) -> List[Tuple[GTMF, Dict]]:
        """
        Extract GTMFs from a batch of EHR cases.

        This method processes multiple EHR cases in sequence, applying the same
        extraction logic to each case.

        Args:
            ehr_cases: List of EHR case dictionaries, each containing 'text' field
                      and optional metadata (subject_id, hadm_id, row_id).
            use_llm_judge: Whether to use LLM judge for quality assessment.
                          If None, uses instance default.

        Returns:
            List of tuples (GTMF, quality_assessment_dict) for each case.
        """
        logger.info(f"GTMFAgent: Starting batch extraction for {len(ehr_cases)} cases")

        results = []
        successful = 0
        failed = 0

        for idx, case in enumerate(ehr_cases, 1):
            case_id = case.get('hadm_id', case.get('row_id', idx))
            logger.info(f"  Processing case {idx}/{len(ehr_cases)} (ID: {case_id})")

            try:
                # Extract medical text
                medical_text = case.get('text', '')
                if not medical_text:
                    logger.warning(f"  Case {case_id}: Empty text, skipping")
                    failed += 1
                    continue

                # Perform extraction with or without judge
                if use_llm_judge or (use_llm_judge is None and self.include_llm_judge):
                    gtmf, quality_report = self.extract_with_llm_judge(medical_text)
                else:
                    gtmf, quality_report = self.extract_with_quality_assessment(medical_text)

                # Add metadata from case
                gtmf.subject_id = case.get('subject_id', gtmf.subject_id)
                gtmf.hadm_id = case.get('hadm_id', gtmf.hadm_id)
                gtmf.row_id = case.get('row_id', gtmf.row_id)

                # Add light case filter result if present
                if 'light_case_filter' in case:
                    quality_report['light_case_filter'] = case['light_case_filter']

                # Tag as light common case
                quality_report['case_type'] = 'LIGHT_COMMON_SYMPTOMS'

                results.append((gtmf, quality_report))
                successful += 1

                logger.info(f"  ✓ Case {case_id}: Extraction successful")

            except Exception as e:
                logger.error(f"  ✗ Case {case_id}: Extraction failed - {e}")
                failed += 1
                continue

        logger.info(f"GTMFAgent: Batch extraction complete - {successful} successful, {failed} failed")

        return results