import json
import logging
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from Utils.llms_utils import load_gpt_model, chat_generate
from Models.classes import GTMF

logger = logging.getLogger(__name__)

@dataclass
class GTMFJudgmentScore:
    """Comprehensive LLM judgment scores for GTMF quality"""
    # Core evaluation dimensions (0-10 scale)
    completeness_score: float      # How completely the GTMF captures the medical text
    accuracy_score: float          # How accurate the extracted information is
    consistency_score: float       # Internal consistency within the GTMF
    medical_relevance_score: float # Clinical appropriateness and relevance
    structure_score: float         # Proper formatting and organization
    
    # Overall scores
    overall_score: float           # Weighted average of all dimensions
    confidence_level: float        # Judge's confidence in the assessment (0-1)
    
    # Detailed feedback
    strengths: List[str]           # What the GTMF does well
    weaknesses: List[str]          # Areas for improvement
    critical_issues: List[str]     # Serious problems that need attention
    recommendations: List[str]     # Specific improvement suggestions
    
    # Field-specific scores
    symptoms_quality: float        # Quality of symptom extraction (0-10)
    diagnoses_quality: float       # Quality of diagnosis extraction (0-10)
    treatments_quality: float     # Quality of treatment extraction (0-10)
    demographics_quality: float   # Quality of demographic information (0-10)
    
    # Meta information
    judgment_reasoning: str        # LLM's reasoning for the scores
    processing_notes: str          # Any processing issues or notes

class GTMFLLMJudge:
    """Advanced LLM judge for comprehensive GTMF quality evaluation"""
    
    def __init__(self, model_name: str = 'gpt-4', temperature: float = 0.1):
        """
        Initialize the GTMF LLM Judge
        
        Args:
            model_name: Azure AI model to use for judgment
            temperature: Temperature for LLM responses (lower = more consistent)
        """
        self.llm = load_gpt_model(model_name=model_name, temperature=temperature, max_tokens=2048)
        self.model_name = model_name
        self.temperature = temperature
        
        # Define the comprehensive evaluation prompt
        self.evaluation_prompt_template = """You are a senior medical informatics expert and clinical documentation specialist. Your task is to comprehensively evaluate the quality of a Ground Truth Medical Form (GTMF) extraction from a clinical note.

**EVALUATION FRAMEWORK:**

**1. COMPLETENESS (0-10):** How thoroughly does the GTMF capture all relevant medical information from the source text?
- 9-10: Captures virtually all relevant information with minimal omissions
- 7-8: Captures most important information with minor gaps
- 5-6: Captures essential information but misses some important details
- 3-4: Captures basic information but significant gaps present
- 1-2: Major information gaps, many important details missing
- 0: Severely incomplete or empty

**2. ACCURACY (0-10):** How accurate and medically correct is the extracted information?
- 9-10: All extractions are medically accurate and correctly interpreted
- 7-8: Most extractions accurate with minor interpretation issues
- 5-6: Generally accurate but some medical inaccuracies present
- 3-4: Multiple accuracy issues that could affect clinical utility
- 1-2: Significant medical inaccuracies that could be harmful
- 0: Severely inaccurate or completely wrong information

**3. CONSISTENCY (0-10):** How internally consistent is the GTMF data?
- 9-10: Perfect internal consistency across all fields
- 7-8: Generally consistent with minor contradictions
- 5-6: Some inconsistencies that don't affect core meaning
- 3-4: Notable inconsistencies that create confusion
- 1-2: Major contradictions between different sections
- 0: Severely inconsistent or contradictory

**4. MEDICAL RELEVANCE (0-10):** How clinically relevant and appropriate are the extractions?
- 9-10: All extractions are highly clinically relevant and appropriate
- 7-8: Most extractions relevant with good clinical insight
- 5-6: Generally relevant but some tangential information
- 3-4: Mixed relevance with some clinically inappropriate extractions
- 1-2: Poor clinical relevance, inappropriate extractions
- 0: Clinically irrelevant or inappropriate

**5. STRUCTURE (0-10):** How well-organized and properly formatted is the GTMF?
- 9-10: Perfectly organized with excellent use of GTMF structure
- 7-8: Well-organized with minor structural issues
- 5-6: Adequately structured but some organizational problems
- 3-4: Poor organization affecting usability
- 1-2: Badly structured, difficult to use
- 0: No clear structure or completely disorganized

**FIELD-SPECIFIC EVALUATION:**
Rate each field's extraction quality (0-10):
- **Symptoms:** Appropriateness, completeness, clinical accuracy
- **Diagnoses:** Medical accuracy, specificity, clinical appropriateness  
- **Treatments:** Relevance, completeness, medical appropriateness
- **Demographics:** Accuracy, completeness, consistency

**EVALUATION INSTRUCTIONS:**
1. Read the original clinical text carefully
2. Examine the GTMF extraction thoroughly
3. Evaluate each dimension using the 0-10 scale
4. Provide specific strengths, weaknesses, and recommendations
5. Give an overall assessment with confidence level

**Your response must be in this exact JSON format:**
```json
{
  "completeness_score": 0.0,
  "accuracy_score": 0.0,
  "consistency_score": 0.0,
  "medical_relevance_score": 0.0,
  "structure_score": 0.0,
  "overall_score": 0.0,
  "confidence_level": 0.0,
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "critical_issues": ["issue1", "issue2"],
  "recommendations": ["rec1", "rec2"],
  "symptoms_quality": 0.0,
  "diagnoses_quality": 0.0,
  "treatments_quality": 0.0,
  "demographics_quality": 0.0,
  "judgment_reasoning": "Detailed explanation of scoring rationale",
  "processing_notes": "Any additional notes or observations"
}
```

**CRITICAL:** Ensure all scores are on a 0-10 scale, and confidence_level is 0-1."""

    def judge_gtmf_quality(self, original_text: str, gtmf_instance: GTMF, 
                          context: Optional[Dict] = None) -> GTMFJudgmentScore:
        """
        Perform comprehensive LLM-based judgment of GTMF quality
        
        Args:
            original_text: The original clinical text
            gtmf_instance: The extracted GTMF instance
            context: Optional context information (e.g., extraction metadata)
            
        Returns:
            GTMFJudgmentScore: Comprehensive quality assessment
        """
        logger.info("Starting LLM-based GTMF quality judgment...")
        
        try:
            # Prepare the evaluation input
            gtmf_dict = gtmf_instance.model_dump()
            evaluation_input = self._prepare_evaluation_input(original_text, gtmf_dict, context)
            
            # Get LLM judgment
            judgment_response = self._get_llm_judgment(evaluation_input)
            
            # Parse and validate the response
            judgment_scores = self._parse_judgment_response(judgment_response)
            
            logger.info(f"GTMF LLM judgment completed. Overall score: {judgment_scores.overall_score:.1f}/10")
            return judgment_scores
            
        except Exception as e:
            logger.error(f"Error during GTMF LLM judgment: {e}", exc_info=True)
            return self._create_error_judgment(str(e))
    
    def _prepare_evaluation_input(self, original_text: str, gtmf_dict: Dict, 
                                context: Optional[Dict] = None) -> str:
        """Prepare the input for LLM evaluation"""
        
        # Summarize GTMF for evaluation
        gtmf_summary = self._create_gtmf_summary(gtmf_dict)
        
        # Add context information if available
        context_info = ""
        if context:
            context_info = f"\n**EXTRACTION CONTEXT:**\n{json.dumps(context, indent=2)}\n"
        
        evaluation_input = f"""**ORIGINAL CLINICAL TEXT:**
{original_text}

**EXTRACTED GTMF:**
{gtmf_summary}
{context_info}
**TASK:** Evaluate the GTMF extraction quality using the provided framework and respond in the specified JSON format."""
        
        return evaluation_input
    
    def _create_gtmf_summary(self, gtmf_dict: Dict) -> str:
        """Create a readable summary of the GTMF for evaluation"""
        
        summary_parts = []
        
        # Core Fields Summary
        core_fields = gtmf_dict.get("Core_Fields", {})
        
        # Symptoms
        symptoms = core_fields.get("Symptoms", [])
        if symptoms:
            symptom_list = []
            for symptom in symptoms:
                desc = symptom.get("description", "")
                onset = symptom.get("onset", "")
                duration = symptom.get("duration", "")
                severity = symptom.get("severity", "")
                
                symptom_str = f"'{desc}'"
                if onset and onset != "not provided":
                    symptom_str += f" (onset: {onset})"
                if duration and duration != "not provided":
                    symptom_str += f" (duration: {duration})"
                if severity and severity != "not provided":
                    symptom_str += f" (severity: {severity})"
                
                symptom_list.append(symptom_str)
            
            summary_parts.append(f"**SYMPTOMS ({len(symptoms)}):**\n" + "\n".join(f"- {s}" for s in symptom_list))
        else:
            summary_parts.append("**SYMPTOMS:** None extracted")
        
        # Diagnoses
        diagnoses = core_fields.get("Diagnoses", [])
        if diagnoses:
            diagnosis_list = []
            for diagnosis in diagnoses:
                primary = diagnosis.get("primary", "")
                notes = diagnosis.get("notes", "")
                
                diag_str = f"'{primary}'"
                if notes and notes != "not provided":
                    diag_str += f" (notes: {notes})"
                
                diagnosis_list.append(diag_str)
            
            summary_parts.append(f"**DIAGNOSES ({len(diagnoses)}):**\n" + "\n".join(f"- {d}" for d in diagnosis_list))
        else:
            summary_parts.append("**DIAGNOSES:** None extracted")
        
        # Treatments
        treatments = core_fields.get("Treatment_Options", [])
        if treatments:
            treatment_list = []
            for treatment in treatments:
                procedure = treatment.get("procedure", "")
                details = treatment.get("details", "")
                medications = treatment.get("medications", [])
                
                treat_str = f"'{procedure}'"
                if details and details != "not provided":
                    treat_str += f" (details: {details})"
                if medications:
                    med_names = [m.get("name", "") for m in medications if m.get("name")]
                    if med_names:
                        treat_str += f" (medications: {', '.join(med_names)})"
                
                treatment_list.append(treat_str)
            
            summary_parts.append(f"**TREATMENTS ({len(treatments)}):**\n" + "\n".join(f"- {t}" for t in treatment_list))
        else:
            summary_parts.append("**TREATMENTS:** None extracted")
        
        # Context Fields Summary
        context_fields = gtmf_dict.get("Context_Fields", {})
        
        # Demographics
        demographics = context_fields.get("Patient_Demographics", {})
        if demographics:
            demo_info = []
            for key, value in demographics.items():
                if value and value != "not provided":
                    demo_info.append(f"{key}: {value}")
            
            if demo_info:
                summary_parts.append(f"**DEMOGRAPHICS:**\n" + "\n".join(f"- {d}" for d in demo_info))
            else:
                summary_parts.append("**DEMOGRAPHICS:** No valid demographic data")
        
        # Medical History
        history = context_fields.get("Medical_History", {})
        if history and isinstance(history, dict):
            past_history = history.get("Past_Medical_History", "")
            if past_history and past_history != "not provided":
                summary_parts.append(f"**MEDICAL HISTORY:** {past_history}")
            else:
                summary_parts.append("**MEDICAL HISTORY:** Not provided")
        
        # Allergies
        allergies = context_fields.get("Allergies", [])
        if allergies:
            summary_parts.append(f"**ALLERGIES:** {', '.join(allergies)}")
        else:
            summary_parts.append("**ALLERGIES:** None specified")
        
        # Additional Context
        additional = gtmf_dict.get("Additional_Context", {})
        chief_complaint = additional.get("Chief_Complaint", "")
        if chief_complaint and chief_complaint != "not provided":
            summary_parts.append(f"**CHIEF COMPLAINT:** {chief_complaint}")
        
        return "\n\n".join(summary_parts)
    
    def _get_llm_judgment(self, evaluation_input: str) -> str:
        """Get the LLM's judgment on the GTMF quality"""
        
        messages = [
            {"role": "system", "content": self.evaluation_prompt_template},
            {"role": "user", "content": evaluation_input}
        ]
        
        try:
            response = chat_generate(self.llm, messages)
            
            if response.startswith("[ERROR"):
                raise Exception(f"LLM error: {response}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting LLM judgment: {e}")
            raise
    
    def _parse_judgment_response(self, response: str) -> GTMFJudgmentScore:
        """Parse the LLM's judgment response into structured scores"""
        
        try:
            # Extract JSON from response
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in LLM response")
            
            # Parse JSON
            judgment_data = json.loads(json_str)
            
            # Validate and convert scores
            judgment_scores = GTMFJudgmentScore(
                completeness_score=float(judgment_data.get("completeness_score", 0.0)),
                accuracy_score=float(judgment_data.get("accuracy_score", 0.0)),
                consistency_score=float(judgment_data.get("consistency_score", 0.0)),
                medical_relevance_score=float(judgment_data.get("medical_relevance_score", 0.0)),
                structure_score=float(judgment_data.get("structure_score", 0.0)),
                overall_score=float(judgment_data.get("overall_score", 0.0)),
                confidence_level=float(judgment_data.get("confidence_level", 0.5)),
                strengths=judgment_data.get("strengths", []),
                weaknesses=judgment_data.get("weaknesses", []),
                critical_issues=judgment_data.get("critical_issues", []),
                recommendations=judgment_data.get("recommendations", []),
                symptoms_quality=float(judgment_data.get("symptoms_quality", 0.0)),
                diagnoses_quality=float(judgment_data.get("diagnoses_quality", 0.0)),
                treatments_quality=float(judgment_data.get("treatments_quality", 0.0)),
                demographics_quality=float(judgment_data.get("demographics_quality", 0.0)),
                judgment_reasoning=judgment_data.get("judgment_reasoning", ""),
                processing_notes=judgment_data.get("processing_notes", "")
            )
            
            # Validate score ranges
            judgment_scores = self._validate_scores(judgment_scores)
            
            return judgment_scores
            
        except Exception as e:
            logger.error(f"Error parsing LLM judgment response: {e}")
            logger.debug(f"Raw response: {response}")
            raise ValueError(f"Failed to parse LLM judgment: {e}")
    
    def _validate_scores(self, scores: GTMFJudgmentScore) -> GTMFJudgmentScore:
        """Validate and clamp scores to appropriate ranges"""
        
        # Clamp 0-10 scores
        ten_scale_fields = [
            'completeness_score', 'accuracy_score', 'consistency_score',
            'medical_relevance_score', 'structure_score', 'overall_score',
            'symptoms_quality', 'diagnoses_quality', 'treatments_quality',
            'demographics_quality'
        ]
        
        for field in ten_scale_fields:
            value = getattr(scores, field)
            setattr(scores, field, max(0.0, min(10.0, value)))
        
        # Clamp confidence level to 0-1
        scores.confidence_level = max(0.0, min(1.0, scores.confidence_level))
        
        # Ensure lists are actually lists
        list_fields = ['strengths', 'weaknesses', 'critical_issues', 'recommendations']
        for field in list_fields:
            value = getattr(scores, field)
            if not isinstance(value, list):
                setattr(scores, field, [])
        
        # Ensure string fields are strings
        string_fields = ['judgment_reasoning', 'processing_notes']
        for field in string_fields:
            value = getattr(scores, field)
            if not isinstance(value, str):
                setattr(scores, field, str(value))
        
        return scores
    
    def _create_error_judgment(self, error_message: str) -> GTMFJudgmentScore:
        """Create a default judgment score when evaluation fails"""
        
        return GTMFJudgmentScore(
            completeness_score=0.0,
            accuracy_score=0.0,
            consistency_score=0.0,
            medical_relevance_score=0.0,
            structure_score=0.0,
            overall_score=0.0,
            confidence_level=0.0,
            strengths=[],
            weaknesses=["Evaluation failed"],
            critical_issues=[f"LLM judgment error: {error_message}"],
            recommendations=["Manual review required"],
            symptoms_quality=0.0,
            diagnoses_quality=0.0,
            treatments_quality=0.0,
            demographics_quality=0.0,
            judgment_reasoning=f"Evaluation failed due to error: {error_message}",
            processing_notes=f"Error occurred during LLM judgment: {error_message}"
        )
    
    def generate_quality_report(self, judgment_scores: GTMFJudgmentScore, 
                              include_details: bool = True) -> str:
        """Generate a human-readable quality report from judgment scores"""
        
        # Overall assessment
        overall_grade = self._score_to_grade(judgment_scores.overall_score)
        
        report_lines = [
            "📋 GTMF QUALITY ASSESSMENT REPORT",
            "=" * 50,
            f"Overall Grade: {overall_grade} ({judgment_scores.overall_score:.1f}/10)",
            f"Confidence Level: {judgment_scores.confidence_level:.1%}",
            ""
        ]
        
        # Dimensional scores
        report_lines.extend([
            "📊 DIMENSIONAL SCORES:",
            f"├─ Completeness: {judgment_scores.completeness_score:.1f}/10",
            f"├─ Accuracy: {judgment_scores.accuracy_score:.1f}/10",
            f"├─ Consistency: {judgment_scores.consistency_score:.1f}/10",
            f"├─ Medical Relevance: {judgment_scores.medical_relevance_score:.1f}/10",
            f"└─ Structure: {judgment_scores.structure_score:.1f}/10",
            ""
        ])
        
        # Field-specific scores
        report_lines.extend([
            "🏥 FIELD-SPECIFIC SCORES:",
            f"├─ Symptoms: {judgment_scores.symptoms_quality:.1f}/10",
            f"├─ Diagnoses: {judgment_scores.diagnoses_quality:.1f}/10",
            f"├─ Treatments: {judgment_scores.treatments_quality:.1f}/10",
            f"└─ Demographics: {judgment_scores.demographics_quality:.1f}/10",
            ""
        ])
        
        if include_details:
            # Strengths
            if judgment_scores.strengths:
                report_lines.extend([
                    "✅ STRENGTHS:",
                    *[f"• {strength}" for strength in judgment_scores.strengths],
                    ""
                ])
            
            # Weaknesses
            if judgment_scores.weaknesses:
                report_lines.extend([
                    "⚠️ WEAKNESSES:",
                    *[f"• {weakness}" for weakness in judgment_scores.weaknesses],
                    ""
                ])
            
            # Critical issues
            if judgment_scores.critical_issues:
                report_lines.extend([
                    "🚨 CRITICAL ISSUES:",
                    *[f"• {issue}" for issue in judgment_scores.critical_issues],
                    ""
                ])
            
            # Recommendations
            if judgment_scores.recommendations:
                report_lines.extend([
                    "💡 RECOMMENDATIONS:",
                    *[f"• {rec}" for rec in judgment_scores.recommendations],
                    ""
                ])
            
            # Reasoning
            if judgment_scores.judgment_reasoning:
                report_lines.extend([
                    "🧠 JUDGMENT REASONING:",
                    judgment_scores.judgment_reasoning,
                    ""
                ])
        
        return "\n".join(report_lines)
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numerical score to letter grade"""
        if score >= 9.0:
            return "A+ (Excellent)"
        elif score >= 8.0:
            return "A (Very Good)"
        elif score >= 7.0:
            return "B+ (Good)"
        elif score >= 6.0:
            return "B (Satisfactory)"
        elif score >= 5.0:
            return "C+ (Fair)"
        elif score >= 4.0:
            return "C (Below Average)"
        elif score >= 3.0:
            return "D (Poor)"
        elif score >= 1.0:
            return "F (Very Poor)"
        else:
            return "F- (Unacceptable)"

# Convenience function for quick evaluation
def evaluate_gtmf_with_llm_judge(original_text: str, gtmf_instance: GTMF, 
                                model_name: str = 'gpt-4') -> GTMFJudgmentScore:
    """
    Quick evaluation function using the LLM judge
    
    Args:
        original_text: The original clinical text
        gtmf_instance: The extracted GTMF instance
        model_name: Azure AI model to use for judgment
        
    Returns:
        GTMFJudgmentScore: Comprehensive quality assessment
    """
    judge = GTMFLLMJudge(model_name=model_name)
    return judge.judge_gtmf_quality(original_text, gtmf_instance)