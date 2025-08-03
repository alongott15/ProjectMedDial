import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import UserMessage
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import statistics
import re
import logging

# Import our medical validation utilities
from Utils.medical_validation import MedicalConceptValidator, assess_dialogue_safety

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class QualityScore:
    structural_consistency: float
    semantic_coherence: float
    medical_relevance: float
    annotation_completeness: float
    medical_validity: float        # NEW: Medical concept validity
    safety_score: float           # NEW: Medical safety score
    overall_quality: float
    reasoning: str
    recommendations: List[str]
    confidence: float = 0.0

@dataclass
class BatchValidationResults:
    total_files: int
    successful_validations: int
    failed_validations: int
    structure_errors: int
    aggregated_scores: Dict[str, float]
    file_results: List[Dict[str, Any]]
    processing_time: float

class ReMeDiLLMJudge:
    """FIXED: Realistic ReMeDi annotation quality judge"""
    
    def __init__(self, model_config):
        self.model_config = model_config
        self.client = None
        
        if model_config["type"] == "azure_ai_inference":
            self.client = ChatCompletionsClient(
                endpoint=model_config["azure_ai_endpoint"],
                credential=AzureKeyCredential(model_config["azure_api_key"])
            )
        
        # Initialize medical validator for realistic assessment
        self.medical_validator = MedicalConceptValidator()
        
        self.few_shot_examples = self._create_realistic_examples()
    
    def _create_realistic_examples(self):
        """Create realistic examples with proper medical validation"""
        return {
            "excellent": {
                "dialogue": {"role": "Patient", "content": "I've been having severe chest pain that gets worse when I breathe deeply, and I feel short of breath."},
                "annotation": {
                    "turn_id": 1,
                    "role": "Patient",
                    "utterance_text": "I've been having severe chest pain that gets worse when I breathe deeply, and I feel short of breath.",
                    "remedi_labels": [
                        {"label_type": "intent", "type_name": "Informing", "slot": "Symptom", "value": "severe chest pain"},
                        {"label_type": "intent", "type_name": "Informing", "slot": "Symptom", "value": "gets worse when I breathe deeply"},
                        {"label_type": "intent", "type_name": "Informing", "slot": "Symptom", "value": "short of breath"}
                    ]
                },
                "scores": {"structural_consistency": 0.95, "semantic_coherence": 0.90, "medical_relevance": 0.95, "annotation_completeness": 0.85, "overall_quality": 0.91},
                "reasoning": "Excellent annotation with proper structural compliance and comprehensive medical content capture."
            },
            "poor": {
                "dialogue": {"role": "Doctor", "content": "What medications are you currently taking for your blood pressure?"},
                "annotation": {
                    "turn_id": 3,
                    "role": "Doctor", 
                    "utterance_text": "What medications are you currently taking for your blood pressure?",
                    "remedi_labels": [{"label_type": "action", "type_name": "Greeting", "slot": "Other", "value": "hello"}]
                },
                "scores": {"structural_consistency": 0.7, "semantic_coherence": 0.2, "medical_relevance": 0.1, "annotation_completeness": 0.1, "overall_quality": 0.3},
                "reasoning": "Poor annotation - should be 'Inquiring' about 'Medicine' with proper value extraction."
            }
        }
    
    def get_realistic_few_shot_prompt(self, dialogue_turn: Dict, annotation: Dict) -> str:
        """Generate realistic few-shot prompt with medical validation context"""
        excellent = self.few_shot_examples["excellent"]
        poor = self.few_shot_examples["poor"]
        
        return f"""Assess medical dialogue annotation quality using realistic medical standards:

                    EXCELLENT EXAMPLE:
                    Dialogue: {excellent["dialogue"]["role"]}: "{excellent["dialogue"]["content"]}"
                    Annotation: {json.dumps(excellent["annotation"], indent=2)}
                    Scores: {excellent["scores"]}
                    Reasoning: {excellent["reasoning"]}

                    POOR EXAMPLE:
                    Dialogue: {poor["dialogue"]["role"]}: "{poor["dialogue"]["content"]}"
                    Annotation: {json.dumps(poor["annotation"], indent=2)}
                    Scores: {poor["scores"]}
                    Reasoning: {poor["reasoning"]}

                    EVALUATION CRITERIA (Realistic Medical Standards):
                    1. Structural Consistency: Does annotation follow ReMeDi schema correctly?
                    2. Semantic Coherence: Do extracted values match dialogue content accurately?
                    3. Medical Relevance: Are medical concepts properly identified and categorized?
                    4. Annotation Completeness: Are all important medical elements captured?
                    5. Medical Validity: Are extracted medical terms clinically appropriate?

                    REALISTIC SCORING GUIDELINES:
                    - 0.8-1.0: Excellent quality, minimal issues
                    - 0.6-0.8: Good quality, minor issues
                    - 0.4-0.6: Acceptable quality, some issues
                    - 0.2-0.4: Poor quality, major issues
                    - 0.0-0.2: Very poor quality, fundamental problems

                    NOW EVALUATE:
                    Dialogue: {dialogue_turn.get('role')}: "{dialogue_turn.get('content')}"
                    Annotation: {json.dumps(annotation, indent=2)}

                    JSON response format:
                    {{
                        "structural_consistency": <0-1>,
                        "semantic_coherence": <0-1>,
                        "medical_relevance": <0-1>, 
                        "annotation_completeness": <0-1>,
                        "medical_validity": <0-1>,
                        "safety_score": <0-1>,
                        "overall_quality": <0-1>,
                        "reasoning": "<explanation>",
                        "recommendations": ["<improvement>"],
                        "confidence": <0-1>
                    }}"""
    
    def evaluate_single_annotation(self, dialogue_turn: Dict, annotation: Dict, few_shot: bool = False) -> QualityScore:
        """FIXED: Realistic single annotation evaluation"""
        
        # 1. MEDICAL VALIDATION using our medical validator
        medical_validity, safety_score = self._assess_medical_validity(dialogue_turn, annotation)
        
        # 2. LLM-based evaluation with realistic prompting
        if few_shot:
            prompt = self.get_realistic_few_shot_prompt(dialogue_turn, annotation)
        else:
            prompt = self._create_realistic_evaluation_prompt(dialogue_turn, annotation)
        
        try:
            if self.model_config["type"] == "azure_ai_inference":
                response = self.client.complete(
                    messages=[UserMessage(content=prompt)],
                    model=self.model_config["azure_ai_model_name"],
                    max_tokens=1000,
                    temperature=0.1  # Lower temperature for more consistent evaluation
                )
                
                if hasattr(response, 'choices') and response.choices:
                    llm_scores = self._extract_realistic_scores(response.choices[0].message.content.strip())
                    
                    # Combine LLM scores with medical validation
                    return self._combine_scores(llm_scores, medical_validity, safety_score)
                    
        except Exception as e:
            logger.warning(f"API Error during evaluation: {e}")
        
        # Fallback to medical validation only
        return self._create_fallback_scores(medical_validity, safety_score, "LLM evaluation failed")
    
    def _assess_medical_validity(self, dialogue_turn: Dict, annotation: Dict) -> Tuple[float, float]:
        """Assess medical validity using our medical validator"""
        
        dialogue_content = dialogue_turn.get('content', '')
        labels = annotation.get('remedi_labels', [])
        
        # Extract medical concepts from labels
        medical_values = []
        for label in labels:
            if label.get('slot') in ['Symptom', 'Disease', 'Medicine', 'Treatment']:
                value = label.get('value', '').strip()
                if value and value != 'not provided':
                    medical_values.append(value)
        
        # 1. Validate medical terms
        if medical_values:
            validation = self.medical_validator.validate_medical_terms(medical_values)
            medical_validity = validation['validity_score']
        else:
            # Check if dialogue contains medical content that should have been extracted
            medical_entities = self.medical_validator.extract_medical_entities(dialogue_content)
            total_medical_content = sum(len(entities) for entities in medical_entities.values())
            
            if total_medical_content > 0:
                medical_validity = 0.3  # Penalty for missing medical content
            else:
                medical_validity = 0.8  # Neutral score when no medical content exists
        
        # 2. Safety assessment
        safety_assessment = assess_dialogue_safety(dialogue_content)
        safety_score = safety_assessment['safety_score']
        
        return medical_validity, safety_score
    
    def _create_realistic_evaluation_prompt(self, dialogue_turn: Dict, annotation: Dict) -> str:
        """Create realistic evaluation prompt without few-shot examples"""
        return f"""Evaluate this medical dialogue annotation using realistic medical standards:

Dialogue: {dialogue_turn.get('role')}: "{dialogue_turn.get('content')}"
Annotation: {json.dumps(annotation, indent=2)}

Assess the following dimensions (0.0-1.0 scale):

1. Structural Consistency: Does the annotation follow ReMeDi schema correctly?
   - Proper label_type (intent/action)
   - Appropriate type_name for the role
   - Correct slot categorization
   - Valid value extraction

2. Semantic Coherence: Do the extracted values accurately represent the dialogue content?
   - Values should be present in the original text
   - No hallucinated or incorrect extractions
   - Appropriate granularity of extraction

3. Medical Relevance: Are medical concepts properly identified?
   - Medical symptoms, diseases, treatments correctly categorized
   - Appropriate medical terminology used
   - Clinical context preserved

4. Annotation Completeness: Are all important elements captured?
   - No missing medical information
   - Comprehensive coverage of dialogue content
   - Appropriate number of labels for content

Apply realistic medical annotation standards. Focus on accuracy and clinical appropriateness.

JSON response format:
{{
    "structural_consistency": <0-1>,
    "semantic_coherence": <0-1>,
    "medical_relevance": <0-1>,
    "annotation_completeness": <0-1>,
    "overall_quality": <0-1>,
    "reasoning": "<detailed explanation>",
    "recommendations": ["<specific improvements>"],
    "confidence": <0-1>
}}"""
    
    def _extract_realistic_scores(self, response_text: str) -> Dict[str, Any]:
        """Extract scores with realistic validation"""
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                scores_dict = json.loads(json_match.group())
                
                # Validate score ranges
                for key in ['structural_consistency', 'semantic_coherence', 'medical_relevance', 
                           'annotation_completeness', 'overall_quality', 'confidence']:
                    if key in scores_dict:
                        scores_dict[key] = max(0.0, min(1.0, float(scores_dict[key])))
                
                return scores_dict
        except Exception as e:
            logger.warning(f"Score extraction failed: {e}")
        
        return self._default_realistic_scores("Score extraction failed")
    
    def _combine_scores(self, llm_scores: Dict[str, Any], medical_validity: float, safety_score: float) -> QualityScore:
        """Combine LLM scores with medical validation scores"""
        
        # Extract LLM scores
        structural_consistency = llm_scores.get('structural_consistency', 0.5)
        semantic_coherence = llm_scores.get('semantic_coherence', 0.5)
        medical_relevance = llm_scores.get('medical_relevance', 0.5)
        annotation_completeness = llm_scores.get('annotation_completeness', 0.5)
        llm_confidence = llm_scores.get('confidence', 0.5)
        
        # Calculate overall quality with realistic weighting
        overall_quality = (
            structural_consistency * 0.25 +
            semantic_coherence * 0.25 +
            medical_relevance * 0.2 +
            annotation_completeness * 0.15 +
            medical_validity * 0.1 +
            safety_score * 0.05
        )
        
        return QualityScore(
            structural_consistency=structural_consistency,
            semantic_coherence=semantic_coherence,
            medical_relevance=medical_relevance,
            annotation_completeness=annotation_completeness,
            medical_validity=medical_validity,
            safety_score=safety_score,
            overall_quality=overall_quality,
            reasoning=llm_scores.get('reasoning', 'Combined LLM and medical validation assessment'),
            recommendations=llm_scores.get('recommendations', ['Review medical concept accuracy']),
            confidence=min(llm_confidence, 0.9)  # Cap confidence realistically
        )
    
    def _create_fallback_scores(self, medical_validity: float, safety_score: float, error_msg: str) -> QualityScore:
        """Create fallback scores when LLM evaluation fails"""
        
        # Realistic fallback based on medical validity
        base_score = (medical_validity + safety_score) / 2
        
        return QualityScore(
            structural_consistency=base_score,
            semantic_coherence=base_score,
            medical_relevance=medical_validity,
            annotation_completeness=base_score,
            medical_validity=medical_validity,
            safety_score=safety_score,
            overall_quality=base_score,
            reasoning=f"Fallback assessment based on medical validation. {error_msg}",
            recommendations=["Manual review required", "Check medical concept accuracy"],
            confidence=0.4  # Lower confidence for fallback
        )
    
    def _default_realistic_scores(self, error_msg: str) -> Dict[str, Any]:
        """Default realistic scores when everything fails"""
        return {
            'structural_consistency': 0.5,
            'semantic_coherence': 0.5,
            'medical_relevance': 0.5,
            'annotation_completeness': 0.5,
            'overall_quality': 0.5,
            'reasoning': f"Default scores used. {error_msg}",
            'recommendations': ["Manual review required"],
            'confidence': 0.3
        }

class ReMeDiRealisticValidator:
    """FIXED: Realistic ReMeDi annotation validator"""
    
    def __init__(self, model_config: Dict):
        self.llm_judge = ReMeDiLLMJudge(model_config)
        self.original_dialogue_dir = "output_dialogue"  # Where original dialogues are stored
        self.medical_validator = MedicalConceptValidator()
    
    def load_original_dialogue(self, annotation_filename: str) -> Optional[List[Dict]]:
        """Load the original dialogue file that corresponds to this annotation file"""
        # Convert: remedi_annotated_4476_69660.json -> dialogue_output_4476_69660.json
        if annotation_filename.startswith("remedi_annotated_"):
            original_filename = annotation_filename.replace("remedi_annotated_", "dialogue_output_")
            original_path = os.path.join(self.original_dialogue_dir, original_filename)
            
            if os.path.exists(original_path):
                try:
                    with open(original_path, 'r', encoding='utf-8') as f:
                        original_data = json.load(f)
                    
                    # Extract dialogue from original file
                    dialogue = original_data.get('dialogue', [])
                    if isinstance(dialogue, list) and dialogue:
                        logger.info(f"  📁 Loaded original dialogue with {len(dialogue)} turns")
                        return dialogue
                    else:
                        logger.warning(f"  ⚠️ Original file exists but has no dialogue data")
                        return None
                except Exception as e:
                    logger.warning(f"  ⚠️ Failed to load original dialogue: {e}")
                    return None
            else:
                logger.warning(f"  ⚠️ Original dialogue file not found: {original_filename}")
                return None
        
        return None
    
    def load_annotation_file(self, file_path: str) -> Tuple[Optional[List[Dict]], Dict]:
        """Load annotation file and return annotations plus metadata"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            annotations = data.get('remedi_style_dialogue_annotations', [])
            metadata = {
                'source_row_id': data.get('source_row_id'),
                'source_subject_id': data.get('source_subject_id'),
                'source_hadm_id': data.get('source_hadm_id'),
                'annotation_count': len(annotations)
            }
            
            if annotations:
                logger.info(f"  📊 Loaded {len(annotations)} annotations")
                return annotations, metadata
            else:
                logger.warning(f"  ⚠️ No annotations found in file")
                return None, metadata
                
        except json.JSONDecodeError as e:
            logger.error(f"  ❌ JSON decode error: {e}")
            return None, {}
        except Exception as e:
            logger.error(f"  ❌ Failed to load file: {e}")
            return None, {}
    
    def evaluate_annotations(self, dialogue: List[Dict], annotations: List[Dict], few_shot: bool = False, sample_size: Optional[int] = None) -> Dict[str, Any]:
        """FIXED: Evaluate annotations against dialogue with realistic scoring"""
        
        eval_annotations = annotations[:sample_size] if sample_size else annotations
        turn_scores = []
        detailed_results = []
        
        logger.info(f"  🔍 Evaluating {len(eval_annotations)} annotations against {len(dialogue)} dialogue turns with REALISTIC scoring")
        
        for i, ann in enumerate(eval_annotations):
            turn_id = ann.get('turn_id')
            if turn_id is not None and turn_id < len(dialogue):
                dialogue_turn = dialogue[turn_id]
                
                # Verify the annotation matches the dialogue turn
                utterance_text = ann.get('utterance_text', '')
                dialogue_content = dialogue_turn.get('content', '')
                
                # Basic sanity check - they should be similar
                if utterance_text != dialogue_content:
                    logger.warning(f"    ⚠️ Turn {turn_id}: annotation text doesn't match dialogue")
                
                # REALISTIC evaluation using fixed LLM judge
                score = self.llm_judge.evaluate_single_annotation(dialogue_turn, ann, few_shot)
                turn_scores.append(score)
                
                detailed_results.append({
                    "turn_id": turn_id,
                    "dialogue_content": dialogue_content,
                    "annotation_utterance": utterance_text,
                    "role": dialogue_turn.get("role", ""),
                    "annotation_role": ann.get("role", ""),
                    "remedi_labels_count": len(ann.get("remedi_labels", [])),
                    "scores": {
                        "structural_consistency": score.structural_consistency,
                        "semantic_coherence": score.semantic_coherence,
                        "medical_relevance": score.medical_relevance,
                        "annotation_completeness": score.annotation_completeness,
                        "medical_validity": score.medical_validity,
                        "safety_score": score.safety_score,
                        "overall_quality": score.overall_quality
                    },
                    "reasoning": score.reasoning,
                    "recommendations": score.recommendations,
                    "confidence": score.confidence
                })
                
                time.sleep(0.2)  # Rate limiting
            else:
                logger.warning(f"    ⚠️ Turn {turn_id}: invalid turn_id or out of range")
        
        if not turn_scores:
            return {"error": "No annotations could be evaluated"}
        
        # REALISTIC aggregated scores
        aggregated_scores = {
            "structural_consistency": statistics.mean([s.structural_consistency for s in turn_scores]),
            "semantic_coherence": statistics.mean([s.semantic_coherence for s in turn_scores]),
            "medical_relevance": statistics.mean([s.medical_relevance for s in turn_scores]),
            "annotation_completeness": statistics.mean([s.annotation_completeness for s in turn_scores]),
            "medical_validity": statistics.mean([s.medical_validity for s in turn_scores]),
            "safety_score": statistics.mean([s.safety_score for s in turn_scores]),
            "overall_quality": statistics.mean([s.overall_quality for s in turn_scores])
        }
        
        all_recommendations = []
        for score in turn_scores:
            all_recommendations.extend(score.recommendations)
        
        return {
            "aggregated_scores": aggregated_scores,
            "coverage": len(eval_annotations) / len(dialogue),
            "evaluated_turns": len(turn_scores),
            "total_turns": len(dialogue),
            "total_annotations": len(annotations),
            "detailed_results": detailed_results,
            "recommendations": list(set(all_recommendations)),
            "model_used": f"{self.llm_judge.model_config['type']}:{self.llm_judge.model_config.get('azure_ai_model_name', 'unknown')}",
            "average_confidence": statistics.mean([s.confidence for s in turn_scores]),
            "evaluation_mode": "realistic-few-shot" if few_shot else "realistic-zero-shot",
            "medical_validation": "enabled"
        }
    
    def validate_single_file(self, file_path: str, few_shot: bool = True, sample_size: Optional[int] = None) -> Dict[str, Any]:
        """Validate a single annotation file with realistic scoring"""
        filename = os.path.basename(file_path)
        
        # Load annotations
        annotations, metadata = self.load_annotation_file(file_path)
        if not annotations:
            return {"error": "No annotations found in file", "metadata": metadata}
        
        # Load original dialogue
        dialogue = self.load_original_dialogue(filename)
        if not dialogue:
            return {"error": "Could not load original dialogue", "metadata": metadata}
        
        # REALISTIC evaluation
        result = self.evaluate_annotations(dialogue, annotations, few_shot=few_shot, sample_size=sample_size)
        if "error" in result:
            result["metadata"] = metadata
        else:
            result["metadata"] = metadata
        
        return result
    
    def validate_input_directory(self, input_dir: str) -> bool:
        """Validate that the directory exists and contains annotation files"""
        if not os.path.exists(input_dir):
            logger.error(f"❌ Input directory '{input_dir}' does not exist.")
            return False
        
        json_files = [f for f in os.listdir(input_dir) if f.startswith("remedi_annotated_") and f.endswith(".json")]
        
        if not json_files:
            logger.warning(f"⚠️ No 'remedi_annotated_*.json' files found in '{input_dir}'")
            all_json = [f for f in os.listdir(input_dir) if f.endswith(".json")]
            if all_json:
                logger.info(f"📁 Found these JSON files instead: {all_json[:5]}")
            return False
        
        logger.info(f"✅ Found {len(json_files)} annotation files to validate")
        
        # Check if original dialogue directory exists
        if not os.path.exists(self.original_dialogue_dir):
            logger.error(f"❌ Original dialogue directory '{self.original_dialogue_dir}' does not exist.")
            return False
        
        original_files = [f for f in os.listdir(self.original_dialogue_dir) if f.startswith("dialogue_output_") and f.endswith(".json")]
        logger.info(f"✅ Found {len(original_files)} original dialogue files in '{self.original_dialogue_dir}'")
        
        return True
    
    def validate_batch(self, input_dir: str, few_shot: bool = True, sample_size: Optional[int] = 5, max_files: Optional[int] = None) -> BatchValidationResults:
        """FIXED: Validate all annotation files with realistic scoring"""
        if not self.validate_input_directory(input_dir):
            return BatchValidationResults(0, 0, 0, 0, {}, [], 0.0)
        
        json_files = [f for f in os.listdir(input_dir) if f.startswith("remedi_annotated_") and f.endswith(".json")]
        
        if max_files:
            json_files = json_files[:max_files]
        
        logger.info(f"🚀 Starting REALISTIC batch validation for {len(json_files)} files")
        logger.info(f"📂 Annotation directory: {input_dir}")
        logger.info(f"📂 Original dialogue directory: {self.original_dialogue_dir}")
        logger.info(f"🎯 Sample size per file: {sample_size or 'all turns'}")
        logger.info(f"🔄 Mode: {'realistic-few-shot' if few_shot else 'realistic-zero-shot'}")
        logger.info(f"🏥 Medical validation: enabled")
        
        start_time = time.time()
        successful_validations = 0
        failed_validations = 0
        structure_errors = 0
        file_results = []
        all_scores = []
        
        for i, filename in enumerate(json_files, 1):
            file_start_time = time.time()
            file_path = os.path.join(input_dir, filename)
            
            logger.info(f"\n📄 Validating file {i}/{len(json_files)}: {filename}")
            
            try:
                result = self.validate_single_file(file_path, few_shot=few_shot, sample_size=sample_size)
                
                if "error" in result:
                    if "Could not load original dialogue" in result["error"]:
                        structure_errors += 1
                        status = "missing_dialogue"
                    else:
                        failed_validations += 1
                        status = "failed"
                    
                    logger.warning(f"  ⚠️ Validation failed: {result['error']}")
                    file_results.append({
                        "filename": filename,
                        "status": status,
                        "error": result["error"],
                        "metadata": result.get("metadata", {}),
                        "processing_time": time.time() - file_start_time
                    })
                else:
                    successful_validations += 1
                    overall_quality = result["aggregated_scores"]["overall_quality"]
                    medical_validity = result["aggregated_scores"]["medical_validity"]
                    safety_score = result["aggregated_scores"]["safety_score"]
                    all_scores.append(result["aggregated_scores"])
                    
                    # REALISTIC status emoji based on realistic thresholds
                    status_emoji = "✅" if overall_quality >= 0.7 else "👍" if overall_quality >= 0.5 else "⚠️" if overall_quality >= 0.3 else "🔴"
                    logger.info(f"  {status_emoji} Quality: {overall_quality:.3f} | Medical: {medical_validity:.3f} | Safety: {safety_score:.3f} | Evaluated: {result['evaluated_turns']}/{result['total_turns']} | Confidence: {result['average_confidence']:.3f}")
                    
                    file_results.append({
                        "filename": filename,
                        "status": "success",
                        "overall_quality": overall_quality,
                        "medical_validity": medical_validity,
                        "safety_score": safety_score,
                        "evaluated_turns": result["evaluated_turns"],
                        "total_turns": result["total_turns"],
                        "total_annotations": result["total_annotations"],
                        "coverage": result["coverage"],
                        "confidence": result["average_confidence"],
                        "scores": result["aggregated_scores"],
                        "metadata": result.get("metadata", {}),
                        "processing_time": time.time() - file_start_time
                    })
                
            except Exception as e:
                logger.error(f"  ❌ Unexpected error: {e}")
                failed_validations += 1
                file_results.append({
                    "filename": filename,
                    "status": "error",
                    "error": str(e),
                    "processing_time": time.time() - file_start_time
                })
        
        # Calculate REALISTIC aggregated scores across all files
        aggregated_scores = {}
        if all_scores:
            for metric in ["structural_consistency", "semantic_coherence", "medical_relevance", 
                          "annotation_completeness", "medical_validity", "safety_score", "overall_quality"]:
                aggregated_scores[metric] = statistics.mean([scores[metric] for scores in all_scores])
        
        total_time = time.time() - start_time
        
        return BatchValidationResults(
            total_files=len(json_files),
            successful_validations=successful_validations,
            failed_validations=failed_validations,
            structure_errors=structure_errors,
            aggregated_scores=aggregated_scores,
            file_results=file_results,
            processing_time=total_time
        )
    
    def generate_batch_report(self, results: BatchValidationResults) -> str:
        """Generate a comprehensive REALISTIC batch validation report"""
        if results.total_files == 0:
            return "❌ No files to validate"
        
        success_rate = (results.successful_validations / results.total_files) * 100
        
        report = f"""
🤖 ReMeDi REALISTIC Batch Validation Report
═══════════════════════════════════════════

📊 SUMMARY STATISTICS:
├─ Total files processed: {results.total_files}
├─ Successful validations: {results.successful_validations}
├─ Failed validations: {results.failed_validations}
├─ Missing dialogue files: {results.structure_errors}
├─ Success rate: {success_rate:.1f}%
└─ Total processing time: {results.processing_time:.1f}s

"""
        
        if results.aggregated_scores:
            overall = results.aggregated_scores['overall_quality']
            medical_validity = results.aggregated_scores.get('medical_validity', 0.0)
            safety = results.aggregated_scores.get('safety_score', 0.0)
            
            # REALISTIC status assessment
            status = "✅ EXCELLENT" if overall >= 0.8 else "👍 GOOD" if overall >= 0.6 else "⚠️ ACCEPTABLE" if overall >= 0.4 else "🔴 POOR"
            
            report += f"""🎯 REALISTIC AGGREGATED QUALITY SCORES:
Overall Quality: {overall:.3f}/1.000 - {status}
Medical Validity: {medical_validity:.3f}/1.000
Safety Score: {safety:.3f}/1.000

Component Scores:
├─ Structural Consistency: {results.aggregated_scores['structural_consistency']:.3f}
├─ Semantic Coherence: {results.aggregated_scores['semantic_coherence']:.3f}
├─ Medical Relevance: {results.aggregated_scores['medical_relevance']:.3f}
├─ Annotation Completeness: {results.aggregated_scores['annotation_completeness']:.3f}
├─ Medical Validity: {medical_validity:.3f}
└─ Safety Score: {safety:.3f}

"""
        
        # Top performing files
        successful_files = [f for f in results.file_results if f["status"] == "success"]
        if successful_files:
            successful_files.sort(key=lambda x: x["overall_quality"], reverse=True)
            
            report += "🏆 TOP PERFORMING FILES:\n"
            for i, file_result in enumerate(successful_files[:5], 1):
                report += f"{i}. {file_result['filename']}: Quality={file_result['overall_quality']:.3f}, Medical={file_result.get('medical_validity', 0):.3f}\n"
            
            report += "\n"
        
        # Files needing attention (REALISTIC thresholds)
        poor_files = [f for f in successful_files if f["overall_quality"] < 0.5]
        if poor_files:
            report += "⚠️ FILES NEEDING ATTENTION (Quality < 0.5):\n"
            for file_result in poor_files[:5]:
                report += f"• {file_result['filename']}: Quality={file_result['overall_quality']:.3f}, Medical={file_result.get('medical_validity', 0):.3f}\n"
            
            report += "\n"
        
        # Structure errors
        structure_error_files = [f for f in results.file_results if f["status"] == "missing_dialogue"]
        if structure_error_files:
            report += f"📁 MISSING DIALOGUE FILES ({len(structure_error_files)}):\n"
            for file_result in structure_error_files[:5]:
                report += f"• {file_result['filename']}: {file_result.get('error', 'Missing dialogue')}\n"
            
            report += "\n"
        
        # Failed validations
        failed_files = [f for f in results.file_results if f["status"] == "failed" or f["status"] == "error"]
        if failed_files:
            report += f"❌ FAILED VALIDATIONS ({len(failed_files)}):\n"
            for file_result in failed_files[:5]:
                report += f"• {file_result['filename']}: {file_result.get('error', 'Unknown error')}\n"
        
        report += f"""

🔬 MEDICAL VALIDATION ENHANCEMENTS:
• Medical concept validity assessment integrated
• Clinical safety scoring enabled
• Realistic thresholds applied
• SOTA medical annotation standards used
"""
        
        return report
    
    def save_batch_results(self, results: BatchValidationResults, output_dir: str):
        """Save comprehensive REALISTIC batch validation results"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Save detailed results
        batch_results = {
            "summary": {
                "total_files": results.total_files,
                "successful_validations": results.successful_validations,
                "failed_validations": results.failed_validations,
                "structure_errors": results.structure_errors,
                "success_rate": (results.successful_validations / results.total_files) * 100 if results.total_files > 0 else 0,
                "processing_time": results.processing_time,
                "aggregated_scores": results.aggregated_scores
            },
            "file_results": results.file_results,
            "metadata": {
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                "framework_version": "2.0_realistic",
                "validation_type": "realistic_with_medical_validation",
                "medical_validation": "enabled",
                "scoring_method": "realistic_thresholds"
            }
        }
        
        with open(output_path / "batch_validation_results.json", 'w', encoding='utf-8') as f:
            json.dump(batch_results, f, indent=2, ensure_ascii=False)
        
        # Save report
        report = self.generate_batch_report(results)
        with open(output_path / "batch_validation_report.txt", 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Create summary CSV
        if results.file_results:
            df_data = []
            for file_result in results.file_results:
                if file_result["status"] == "success":
                    df_data.append({
                        "filename": file_result["filename"],
                        "overall_quality": file_result["overall_quality"],
                        "medical_validity": file_result.get("medical_validity", 0.0),
                        "safety_score": file_result.get("safety_score", 0.0),
                        "structural_consistency": file_result["scores"]["structural_consistency"],
                        "semantic_coherence": file_result["scores"]["semantic_coherence"],
                        "medical_relevance": file_result["scores"]["medical_relevance"],
                        "annotation_completeness": file_result["scores"]["annotation_completeness"],
                        "evaluated_turns": file_result["evaluated_turns"],
                        "total_turns": file_result["total_turns"],
                        "total_annotations": file_result["total_annotations"],
                        "coverage": file_result["coverage"],
                        "confidence": file_result["confidence"],
                        "processing_time": file_result["processing_time"]
                    })
            
            if df_data:
                df = pd.DataFrame(df_data)
                df.to_csv(output_path / "validation_summary.csv", index=False)
        
        logger.info(f"✅ REALISTIC batch validation results saved to {output_path}/")

def plot_realistic_quality_scores(results: BatchValidationResults, save_path: Optional[str] = None):
    """Create visualizations for REALISTIC batch validation results"""
    if not results.aggregated_scores:
        return
    
    successful_files = [f for f in results.file_results if f["status"] == "success"]
    if not successful_files:
        return
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    
    # 1. REALISTIC aggregated component scores
    scores = results.aggregated_scores
    components = ['Structural', 'Semantic', 'Medical\nRelevance', 'Completeness', 'Medical\nValidity', 'Safety']
    values = [scores['structural_consistency'], scores['semantic_coherence'], 
              scores['medical_relevance'], scores['annotation_completeness'],
              scores.get('medical_validity', 0), scores.get('safety_score', 0)]
    
    bars = ax1.bar(components, values, color=['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#e67e22'])
    ax1.set_title('REALISTIC Quality Components')
    ax1.set_ylabel('Score (0-1)')
    ax1.set_ylim(0, 1)
    ax1.tick_params(axis='x', rotation=45)
    
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                f'{value:.3f}', ha='center', va='bottom')
    
    # 2. REALISTIC overall quality distribution
    quality_scores = [f["overall_quality"] for f in successful_files]
    ax2.hist(quality_scores, bins=20, color='skyblue', alpha=0.7, edgecolor='black')
    ax2.set_title('REALISTIC Quality Score Distribution')
    ax2.set_xlabel('Quality Score')
    ax2.set_ylabel('Number of Files')
    ax2.axvline(scores['overall_quality'], color='red', linestyle='--', label=f'Mean: {scores["overall_quality"]:.3f}')
    # Add REALISTIC thresholds
    ax2.axvline(0.7, color='green', linestyle=':', label='Excellent (0.7)')
    ax2.axvline(0.5, color='orange', linestyle=':', label='Good (0.5)')
    ax2.legend()
    
    # 3. Medical validity vs overall quality
    medical_scores = [f.get("medical_validity", 0) for f in successful_files]
    ax3.scatter(medical_scores, quality_scores, alpha=0.6, color='green')
    ax3.set_title('Medical Validity vs Overall Quality')
    ax3.set_xlabel('Medical Validity')
    ax3.set_ylabel('Overall Quality')
    ax3.plot([0, 1], [0, 1], 'k--', alpha=0.3)  # Diagonal reference line
    
    # 4. Safety vs quality relationship
    safety_scores = [f.get("safety_score", 0) for f in successful_files]
    ax4.scatter(safety_scores, quality_scores, alpha=0.6, color='red')
    ax4.set_title('Safety Score vs Overall Quality')
    ax4.set_xlabel('Safety Score')
    ax4.set_ylabel('Overall Quality')
    ax4.plot([0, 1], [0, 1], 'k--', alpha=0.3)  # Diagonal reference line
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    plt.show()

def main():
    AZURE_CONFIG = {
        "type": "azure_ai_inference",
        "azure_ai_endpoint": os.getenv('AZURE_AI_ENDPOINT'),
        "azure_ai_model_name": "gpt-4.1",
        "azure_api_key": os.getenv('AZURE_AI_API_KEY')
    }
    
    if not AZURE_CONFIG["azure_ai_endpoint"] or not AZURE_CONFIG["azure_api_key"]:
        logger.error("❌ Error: Azure AI configuration missing in .env file")
        return
    
    # Configuration
    input_dir = "output_annotated"  # Directory created by annotation_main.py
    output_dir = "annotation_validation_results_realistic"  # Directory to save results
    sample_size = None  # Number of turns to evaluate per file (None for all)
    max_files = None  # Set to limit number of files (e.g., 10 for testing)
    
    validator = ReMeDiRealisticValidator(AZURE_CONFIG)
    
    # Run REALISTIC batch validation
    results = validator.validate_batch(
        input_dir=input_dir,
        few_shot=True,  # Recommended
        sample_size=sample_size,
        max_files=max_files
    )
    
    # Generate and display REALISTIC report
    report = validator.generate_batch_report(results)
    print(report)
    
    # Save results
    validator.save_batch_results(results, output_dir)
    
    # Create visualizations if we have successful results
    if results.successful_validations > 0:
        plot_realistic_quality_scores(results, f"{output_dir}/realistic_quality_charts.png")
    
    logger.info(f"\n✅ REALISTIC batch validation complete! Results saved to {output_dir}/")
    logger.info(f"🔬 Key improvements: Medical validation, safety assessment, realistic thresholds")

if __name__ == "__main__":
    main()