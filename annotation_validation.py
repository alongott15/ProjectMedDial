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

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class QualityScore:
    structural_consistency: float
    semantic_coherence: float
    medical_relevance: float
    annotation_completeness: float
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
    def __init__(self, model_config):
        self.model_config = model_config
        self.client = None
        
        if model_config["type"] == "azure_ai_inference":
            self.client = ChatCompletionsClient(
                endpoint=model_config["azure_ai_endpoint"],
                credential=AzureKeyCredential(model_config["azure_api_key"])
            )
        
        self.few_shot_examples = self._create_examples()
    
    def _create_examples(self):
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
                "scores": {"structural_consistency": 1.0, "semantic_coherence": 0.95, "medical_relevance": 1.0, "annotation_completeness": 0.9, "overall_quality": 0.96},
                "reasoning": "Excellent annotation with perfect structural compliance and comprehensive medical content capture."
            },
            "poor": {
                "dialogue": {"role": "Doctor", "content": "What medications are you currently taking for your blood pressure?"},
                "annotation": {
                    "turn_id": 3,
                    "role": "Doctor", 
                    "utterance_text": "What medications are you currently taking for your blood pressure?",
                    "remedi_labels": [{"label_type": "action", "type_name": "Greeting", "slot": "Other", "value": "hello"}]
                },
                "scores": {"structural_consistency": 0.7, "semantic_coherence": 0.0, "medical_relevance": 0.1, "annotation_completeness": 0.0, "overall_quality": 0.2},
                "reasoning": "Incorrect annotation - should be 'Inquiring' about 'Medicine' with proper value extraction."
            }
        }
    
    def get_few_shot_prompt(self, dialogue_turn: Dict, annotation: Dict) -> str:
        excellent = self.few_shot_examples["excellent"]
        poor = self.few_shot_examples["poor"]
        
        return f"""Assess medical dialogue annotation quality using these examples:

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

                    NOW EVALUATE:
                    Dialogue: {dialogue_turn.get('role')}: "{dialogue_turn.get('content')}"
                    Annotation: {json.dumps(annotation, indent=2)}

                    JSON response format:
                    {{
                        "structural_consistency": <0-1>,
                        "semantic_coherence": <0-1>,
                        "medical_relevance": <0-1>, 
                        "annotation_completeness": <0-1>,
                        "overall_quality": <0-1>,
                        "reasoning": "<explanation>",
                        "recommendations": ["<improvement>"],
                        "confidence": <0-1>
                    }}"""
    
    def evaluate_single_annotation(self, dialogue_turn: Dict, annotation: Dict, few_shot: bool = False) -> QualityScore:
        prompt = self.get_few_shot_prompt(dialogue_turn, annotation)
        
        try:
            if self.model_config["type"] == "azure_ai_inference":
                response = self.client.complete(
                    messages=[UserMessage(content=prompt)],
                    model=self.model_config["azure_ai_model_name"],
                    max_tokens=1000,
                    temperature=0.1
                )
                
                if hasattr(response, 'choices') and response.choices:
                    return self._extract_scores(response.choices[0].message.content.strip())
                    
        except Exception as e:
            logger.warning(f"API Error during evaluation: {e}")
        
        return self._default_scores("Evaluation failed")
    
    def _extract_scores(self, response_text: str) -> QualityScore:
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                scores_dict = json.loads(json_match.group())
                return QualityScore(
                    structural_consistency=float(scores_dict.get("structural_consistency", 0.0)),
                    semantic_coherence=float(scores_dict.get("semantic_coherence", 0.0)),
                    medical_relevance=float(scores_dict.get("medical_relevance", 0.0)),
                    annotation_completeness=float(scores_dict.get("annotation_completeness", 0.0)),
                    overall_quality=float(scores_dict.get("overall_quality", 0.0)),
                    reasoning=scores_dict.get("reasoning", ""),
                    recommendations=scores_dict.get("recommendations", []),
                    confidence=float(scores_dict.get("confidence", 0.5))
                )
        except Exception as e:
            logger.warning(f"Score extraction failed: {e}")
        
        return self._default_scores("Score extraction failed")
    
    def _default_scores(self, error_msg: str) -> QualityScore:
        return QualityScore(0.0, 0.0, 0.0, 0.0, 0.0, f"Error: {error_msg}", ["Manual review required"], 0.0)

class ReMeDiFixedValidator:
    def __init__(self, model_config: Dict):
        self.llm_judge = ReMeDiLLMJudge(model_config)
        self.original_dialogue_dir = "output_dialogue"  # Where original dialogues are stored
    
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
        """Evaluate annotations against dialogue"""
        
        eval_annotations = annotations[:sample_size] if sample_size else annotations
        turn_scores = []
        detailed_results = []
        
        logger.info(f"  🔍 Evaluating {len(eval_annotations)} annotations against {len(dialogue)} dialogue turns")
        
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
        
        aggregated_scores = {
            "structural_consistency": statistics.mean([s.structural_consistency for s in turn_scores]),
            "semantic_coherence": statistics.mean([s.semantic_coherence for s in turn_scores]),
            "medical_relevance": statistics.mean([s.medical_relevance for s in turn_scores]),
            "annotation_completeness": statistics.mean([s.annotation_completeness for s in turn_scores]),
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
            "evaluation_mode": "few-shot" if few_shot else "zero-shot"
        }
    
    def validate_single_file(self, file_path: str, few_shot: bool = True, sample_size: Optional[int] = None) -> Dict[str, Any]:
        """Validate a single annotation file"""
        filename = os.path.basename(file_path)
        
        # Load annotations
        annotations, metadata = self.load_annotation_file(file_path)
        if not annotations:
            return {"error": "No annotations found in file", "metadata": metadata}
        
        # Load original dialogue
        dialogue = self.load_original_dialogue(filename)
        if not dialogue:
            return {"error": "Could not load original dialogue", "metadata": metadata}
        
        # Evaluate
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
        """Validate all annotation files in the directory"""
        if not self.validate_input_directory(input_dir):
            return BatchValidationResults(0, 0, 0, 0, {}, [], 0.0)
        
        json_files = [f for f in os.listdir(input_dir) if f.startswith("remedi_annotated_") and f.endswith(".json")]
        
        if max_files:
            json_files = json_files[:max_files]
        
        logger.info(f"🚀 Starting fixed batch validation for {len(json_files)} files")
        logger.info(f"📂 Annotation directory: {input_dir}")
        logger.info(f"📂 Original dialogue directory: {self.original_dialogue_dir}")
        logger.info(f"🎯 Sample size per file: {sample_size or 'all turns'}")
        logger.info(f"🔄 Mode: {'few-shot' if few_shot else 'zero-shot'}")
        
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
                    all_scores.append(result["aggregated_scores"])
                    
                    status_emoji = "✅" if overall_quality >= 0.7 else "👍" if overall_quality >= 0.5 else "⚠️" if overall_quality >= 0.3 else "🔴"
                    logger.info(f"  {status_emoji} Quality: {overall_quality:.3f} | Evaluated: {result['evaluated_turns']}/{result['total_turns']} | Annotations: {result['total_annotations']} | Confidence: {result['average_confidence']:.3f}")
                    
                    file_results.append({
                        "filename": filename,
                        "status": "success",
                        "overall_quality": overall_quality,
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
        
        # Calculate aggregated scores across all files
        aggregated_scores = {}
        if all_scores:
            for metric in ["structural_consistency", "semantic_coherence", "medical_relevance", "annotation_completeness", "overall_quality"]:
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
        """Generate a comprehensive batch validation report"""
        if results.total_files == 0:
            return "❌ No files to validate"
        
        success_rate = (results.successful_validations / results.total_files) * 100
        
        report = f"""
🤖 ReMeDi Fixed Batch Validation Report
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
            status = "✅ EXCELLENT" if overall >= 0.8 else "👍 GOOD" if overall >= 0.6 else "⚠️ MODERATE" if overall >= 0.4 else "🔴 POOR"
            
            report += f"""🎯 AGGREGATED QUALITY SCORES:
Overall Quality: {overall:.3f}/1.000 - {status}

Component Scores:
├─ Structural Consistency: {results.aggregated_scores['structural_consistency']:.3f}
├─ Semantic Coherence: {results.aggregated_scores['semantic_coherence']:.3f}
├─ Medical Relevance: {results.aggregated_scores['medical_relevance']:.3f}
└─ Annotation Completeness: {results.aggregated_scores['annotation_completeness']:.3f}

"""
        
        # Top performing files
        successful_files = [f for f in results.file_results if f["status"] == "success"]
        if successful_files:
            successful_files.sort(key=lambda x: x["overall_quality"], reverse=True)
            
            report += "🏆 TOP PERFORMING FILES:\n"
            for i, file_result in enumerate(successful_files[:5], 1):
                report += f"{i}. {file_result['filename']}: {file_result['overall_quality']:.3f}\n"
            
            report += "\n"
        
        # Files needing attention
        poor_files = [f for f in successful_files if f["overall_quality"] < 0.5]
        if poor_files:
            report += "⚠️ FILES NEEDING ATTENTION:\n"
            for file_result in poor_files[:5]:
                report += f"• {file_result['filename']}: {file_result['overall_quality']:.3f}\n"
            
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
        
        return report
    
    def save_batch_results(self, results: BatchValidationResults, output_dir: str):
        """Save comprehensive batch validation results"""
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
                "framework_version": "1.0",
                "validation_type": "fixed_with_original_dialogue"
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
        
        logger.info(f"✅ Fixed batch validation results saved to {output_path}/")

def plot_batch_quality_scores(results: BatchValidationResults, save_path: Optional[str] = None):
    """Create visualizations for batch validation results"""
    if not results.aggregated_scores:
        return
    
    successful_files = [f for f in results.file_results if f["status"] == "success"]
    if not successful_files:
        return
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    
    # 1. Aggregated component scores
    scores = results.aggregated_scores
    components = ['Structural', 'Semantic', 'Medical', 'Completeness']
    values = [scores['structural_consistency'], scores['semantic_coherence'], 
              scores['medical_relevance'], scores['annotation_completeness']]
    
    bars = ax1.bar(components, values, color=['#3498db', '#e74c3c', '#2ecc71', '#f39c12'])
    ax1.set_title('Aggregated Quality Components')
    ax1.set_ylabel('Score (0-1)')
    ax1.set_ylim(0, 1)
    
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                f'{value:.3f}', ha='center', va='bottom')
    
    # 2. Overall quality distribution
    quality_scores = [f["overall_quality"] for f in successful_files]
    ax2.hist(quality_scores, bins=20, color='skyblue', alpha=0.7, edgecolor='black')
    ax2.set_title('Overall Quality Score Distribution')
    ax2.set_xlabel('Quality Score')
    ax2.set_ylabel('Number of Files')
    ax2.axvline(scores['overall_quality'], color='red', linestyle='--', label=f'Mean: {scores["overall_quality"]:.3f}')
    ax2.legend()
    
    # 3. Quality vs Coverage scatter
    coverage_scores = [f["coverage"] for f in successful_files]
    ax3.scatter(coverage_scores, quality_scores, alpha=0.6, color='green')
    ax3.set_title('Quality vs Coverage')
    ax3.set_xlabel('Coverage')
    ax3.set_ylabel('Overall Quality')
    
    # 4. Processing time distribution
    processing_times = [f["processing_time"] for f in successful_files]
    ax4.hist(processing_times, bins=15, color='orange', alpha=0.7, edgecolor='black')
    ax4.set_title('Processing Time Distribution')
    ax4.set_xlabel('Processing Time (seconds)')
    ax4.set_ylabel('Number of Files')
    
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
    output_dir = "annotation_validation_results"  # Directory to save results
    sample_size = None  # Number of turns to evaluate per file (None for all)
    max_files = None  # Set to limit number of files (e.g., 10 for testing)
    
    validator = ReMeDiFixedValidator(AZURE_CONFIG)
    
    # Run batch validation
    results = validator.validate_batch(
        input_dir=input_dir,
        few_shot=True,  # Recommended
        sample_size=sample_size,
        max_files=max_files
    )
    
    # Generate and display report
    report = validator.generate_batch_report(results)
    print(report)
    
    # Save results
    validator.save_batch_results(results, output_dir)
    
    # Create visualizations if we have successful results
    if results.successful_validations > 0:
        plot_batch_quality_scores(results, f"{output_dir}/batch_quality_charts.png")
    
    logger.info(f"\n✅ Fixed batch validation complete! Results saved to {output_dir}/")

if __name__ == "__main__":
    main()