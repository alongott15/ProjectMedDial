import logging
import re
from typing import Dict, List, Tuple
from Utils.llms_utils import load_gpt_model, chat_generate 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoachAgent:
    def __init__(self, summarizer_agent, validator_agent, llm_for_coach=None, 
                 sota_realism_threshold=0.6):  # FIXED: Realistic threshold
        """
        FIXED CoachAgent with realistic evaluation thresholds
        """
        if llm_for_coach:
            self.llm = llm_for_coach
        else:
            self.llm = load_gpt_model(temperature=0.1, max_tokens=1200)
        
        self.summarizer = summarizer_agent
        self.validator = validator_agent
        self.sota_realism_threshold = sota_realism_threshold
        
        # FIXED: Realistic quality indicators
        self.quality_indicators = {
            'semantic_quality': {
                'threshold': 0.5,      # Realistic threshold
                'weight': 0.25,        # Balanced weight
                'description': 'Content semantic similarity'
            },
            'medical_coverage': {
                'threshold': 0.4,      # Realistic threshold
                'weight': 0.25,        # Balanced weight
                'description': 'Medical concept coverage'
            },
            'dialogue_naturalness': {
                'threshold': 0.4,      # Realistic threshold
                'weight': 0.25,        # Balanced weight
                'description': 'Natural conversation flow'
            },
            'medical_safety': {
                'threshold': 0.7,      # Keep high for safety
                'weight': 0.25,        # Balanced weight
                'description': 'Medical safety assessment'
            }
        }
        
        self.base_prompt_for_llm_qualitative_review = (
            "You are a senior medical educator and dialogue realism expert. Evaluate this doctor-patient conversation "
            "for authenticity and clinical appropriateness.\n\n"
            
            "**REALISTIC EVALUATION FRAMEWORK:**\n\n"
            
            "**A. CLINICAL AUTHENTICITY (40% weight):**\n"
            "1. **Medical Communication Quality:**\n"
            "   - Professional and empathetic doctor responses\n"
            "   - Appropriate medical inquiry and reasoning\n"
            "   - Safe and responsible medical guidance\n"
            "   - Patient-centered communication approach\n\n"
            
            "2. **Realistic Patient Behavior:**\n"
            "   - Natural information disclosure progression\n"
            "   - Appropriate emotional responses to medical discussion\n"
            "   - Believable patient concerns and questions\n"
            "   - Realistic hesitations and clarifications\n\n"
            
            "**B. CONVERSATION DYNAMICS (35% weight):**\n"
            "3. **Dialogue Flow:**\n"
            "   - Logical progression of medical interview\n"
            "   - Appropriate turn-taking and responses\n"
            "   - Natural conversation development\n"
            "   - Meaningful exchange of information\n\n"
            
            "4. **Communication Effectiveness:**\n"
            "   - Doctor adapts to patient emotional state\n"
            "   - Patient feels heard and understood\n"
            "   - Clear and understandable explanations\n"
            "   - Professional rapport building\n\n"
            
            "**C. MEDICAL SAFETY & APPROPRIATENESS (25% weight):**\n"
            "5. **Clinical Safety:**\n"
            "   - No harmful or inappropriate medical advice\n"
            "   - Appropriate urgency and follow-up recommendations\n"
            "   - Professional medical communication standards\n"
            "   - Safe and ethical medical practice\n\n"
            
            "**EVALUATION GUIDELINES:**\n"
            "- Apply realistic standards for medical dialogue evaluation\n"
            "- Some imperfections are normal in real conversations\n"
            "- Prioritize medical safety and clinical appropriateness\n"
            "- Natural conversation flow is important but not perfect\n"
            "- Focus on overall authenticity and medical value\n\n"
            
            "**ASSESSMENT CRITERIA:**\n"
            "Consider dialogue REALISTIC if:\n"
            "✓ Medical communication is safe and appropriate\n"
            "✓ Patient behavior seems natural and believable\n"
            "✓ Doctor shows empathy and professionalism\n"
            "✓ Conversation flows logically\n"
            "✓ Information exchange serves medical purpose\n\n"
            
            "**EVALUATION OUTPUT:**\n"
            "Start with 'DIALOGUE REALISTIC:' or 'DIALOGUE UNREALISTIC:'\n"
            "Focus on whether the conversation represents a plausible medical encounter."
        )
        
        logger.info("FIXED CoachAgent initialized with realistic evaluation thresholds")
    
    def _analyze_sota_metrics(self, sota_scores: Dict) -> Dict[str, float]:
        """Analyze SOTA evaluation metrics with realistic interpretation"""
        
        # Extract key SOTA metrics with fallback values
        analysis = {
            'semantic_quality': sota_scores.get('bertscore_f1', 0.0),
            'medical_coverage': sota_scores.get('overall_medical_coverage', 0.0),
            'dialogue_naturalness': sota_scores.get('dialogue_naturalness', 0.0),
            'progressive_disclosure': sota_scores.get('progressive_disclosure_quality', 0.0),
            'medical_safety': sota_scores.get('safety_score', 0.0),
            'conversation_flow': sota_scores.get('conversation_flow_quality', 0.0),
            'overall_dialogue_quality': sota_scores.get('overall_dialogue_quality', 0.0)
        }
        
        # Add derived quality indicators
        analysis['empathy_quality'] = sota_scores.get('dialogue_empathy', 0.0)
        analysis['professionalism'] = sota_scores.get('dialogue_professionalism', 0.0)
        
        return analysis
    
    def _determine_realism_from_feedback(self, feedback_text: str, dimensional_scores: Dict[str, float], 
                                       sota_analysis: Dict[str, float]) -> bool:
        """FIXED: Realistic realism determination"""
        feedback_lower = feedback_text.strip().lower()
        
        # Primary signal: LLM's explicit assessment
        explicit_realistic = feedback_lower.startswith("dialogue realistic:")
        explicit_unrealistic = feedback_lower.startswith("dialogue unrealistic:")
        
        if explicit_realistic:
            primary_signal = True
            primary_confidence = 0.8
        elif explicit_unrealistic:
            primary_signal = False
            primary_confidence = 0.8
        else:
            # Fallback based on dimensional scores
            overall_score = dimensional_scores.get('overall', dimensional_scores.get('authenticity', 3.0))
            primary_signal = overall_score >= 3.0
            primary_confidence = 0.6
        
        # Secondary validation: SOTA metrics validation
        key_metrics = {
            'medical_safety': sota_analysis.get('medical_safety', 0.0),
            'semantic_quality': sota_analysis.get('semantic_quality', 0.0),
        }
        
        # REALISTIC validation thresholds
        safety_ok = key_metrics['medical_safety'] > 0.6  # Safety is critical
        semantic_ok = key_metrics['semantic_quality'] > 0.3  # Realistic threshold
        
        sota_validation_score = (safety_ok * 0.7 + semantic_ok * 0.3)
        
        # FIXED: Realistic decision weights
        combined_realism_score = (
            primary_signal * primary_confidence * 0.6 +    # Expert assessment
            sota_validation_score * 0.4                    # SOTA metrics
        )
        
        # SAFETY OVERRIDE: If safety is poor, override positive assessment
        if key_metrics['medical_safety'] < 0.5:
            logger.warning(f"[Safety Override] Low safety score {key_metrics['medical_safety']:.2f} - marking unrealistic")
            return False
        
        # EXPERT OVERRIDE: If expert says realistic and safety is acceptable
        if explicit_realistic and key_metrics['medical_safety'] > 0.6:
            logger.info(f"[Expert Override] Expert assessment confirmed with good safety")
            return True
        
        logger.info(f"[Realistic Coach] Realism determination: Expert={primary_signal}, "
                   f"Safety={key_metrics['medical_safety']:.2f}, "
                   f"Combined={combined_realism_score:.2f}")
        
        # REALISTIC THRESHOLD
        return combined_realism_score >= self.sota_realism_threshold
    
    def _get_llm_qualitative_assessment(self, dialogue_text: str, sota_analysis: Dict[str, float]) -> Tuple[bool, str, Dict[str, float]]:
        """Realistic qualitative assessment"""
        
        # Create realistic context summary
        key_metrics = {
            'Medical Safety': sota_analysis['medical_safety'],
            'Semantic Quality': sota_analysis['semantic_quality'], 
            'Medical Coverage': sota_analysis['medical_coverage']
        }
        
        sota_summary = "Quality Indicators:\n" + "\n".join([
            f"- {name}: {score:.2f} {'✓' if score > 0.5 else '○'}"
            for name, score in key_metrics.items()
        ])
        
        prompt_to_llm = (
            f"{sota_summary}\n\n"
            f"DIALOGUE TO EVALUATE:\n{dialogue_text}\n\n"
            "Evaluate this medical dialogue for realism and clinical appropriateness:\n"
            "1. Is the medical communication safe and appropriate?\n"
            "2. Does the patient behavior seem natural and believable?\n"
            "3. Does the doctor show empathy and professionalism?\n"
            "4. Does the conversation serve a meaningful medical purpose?\n\n"
            "Apply realistic standards - some imperfections are normal in real conversations.\n"
            "Focus on overall authenticity and clinical value.\n\n"
            "Start with 'DIALOGUE REALISTIC:' or 'DIALOGUE UNREALISTIC:' and provide specific evidence."
        )
        
        messages = [
            {"role": "system", "content": self.base_prompt_for_llm_qualitative_review},
            {"role": "user", "content": prompt_to_llm}
        ]
        
        try:
            llm_feedback_text = chat_generate(self.llm, messages)
            logger.info(f"[Realistic Coach] LLM Assessment:\n{llm_feedback_text}")

            dimensional_scores = self._extract_dimensional_scores(llm_feedback_text)
            is_qualitatively_realistic = self._determine_realism_from_feedback(
                llm_feedback_text, dimensional_scores, sota_analysis
            )
            
            return is_qualitatively_realistic, llm_feedback_text, dimensional_scores
            
        except Exception as e:
            logger.error(f"Error in LLM qualitative assessment: {e}")
            return False, "LLM assessment failed", {'overall': 2.0}

    def _extract_dimensional_scores(self, feedback_text: str) -> Dict[str, float]:
        """Extract dimensional scores with realistic interpretation"""
        scores = {}
        
        patterns = {
            'authenticity': r'(?:authenticity|realistic|authentic)[:\s]*(\d+(?:\.\d+)?)',
            'medical_quality': r'(?:medical|clinical|professional)[:\s]*(\d+(?:\.\d+)?)',
            'communication': r'(?:communication|empathy|rapport)[:\s]*(\d+(?:\.\d+)?)',
            'safety': r'(?:safety|safe|appropriate)[:\s]*(\d+(?:\.\d+)?)',
            'overall': r'(?:overall|total|final)[:\s]*(\d+(?:\.\d+)?)'
        }
        
        text_lower = feedback_text.lower()
        
        for dimension, pattern in patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                try:
                    score = float(match.group(1))
                    if score <= 1.0:
                        score *= 5
                    scores[dimension] = min(5.0, score)
                except ValueError:
                    scores[dimension] = 3.0
        
        # REALISTIC default scoring
        for dimension in patterns.keys():
            if dimension not in scores:
                if any(word in text_lower for word in ["realistic", "authentic", "appropriate", "professional"]):
                    scores[dimension] = 3.5
                elif any(word in text_lower for word in ["good", "satisfactory", "adequate"]):
                    scores[dimension] = 3.0
                elif any(word in text_lower for word in ["poor", "unrealistic", "inappropriate"]):
                    scores[dimension] = 2.0
                else:
                    scores[dimension] = 3.0  # Neutral default
        
        return scores

    def review_dialogue(self, dialogue_text: str, ground_truth: dict) -> Tuple[str, str]:
        """FIXED dialogue review with realistic evaluation"""
        final_feedback_parts = []

        logger.info("Starting realistic SOTA dialogue review...")

        # 1. Content extraction
        try:
            _, structured_annotations = self.summarizer.summarize_and_annotate(dialogue_text)
        except Exception as e:
            logger.error(f"Error in summarization: {e}")
            structured_annotations = {"symptoms": [], "diagnoses": [], "treatments": []}
        
        # 2. SOTA Evaluation with realistic metrics
        try:
            conversation_info = {
                'dialogue_text': dialogue_text,
                'transcript': dialogue_text,
                'extracted_info': structured_annotations
            }
            
            sota_evaluation = self.validator.evaluate(ground_truth, conversation_info)
            
            # Analyze SOTA metrics realistically
            sota_analysis = self._analyze_sota_metrics(sota_evaluation)
            
            logger.info(f"[Realistic Coach] Key metrics: Semantic={sota_analysis['semantic_quality']:.3f}, "
                       f"Naturalness={sota_analysis['dialogue_naturalness']:.3f}, "
                       f"Safety={sota_analysis['medical_safety']:.3f}")
            
        except Exception as e:
            logger.error(f"Error in SOTA evaluation: {e}")
            sota_evaluation = {'overall_sota_score': 0.0}
            sota_analysis = {key: 0.0 for key in ['semantic_quality', 'medical_coverage', 
                                                 'dialogue_naturalness', 'progressive_disclosure',
                                                 'medical_safety']}

        # 3. SOTA Metrics Summary
        sota_summary = self._create_realistic_sota_summary(sota_evaluation, sota_analysis)
        final_feedback_parts.append(sota_summary)

        # 4. Realistic LLM qualitative assessment
        try:
            is_qualitatively_realistic, llm_feedback, dimensional_scores = self._get_llm_qualitative_assessment(
                dialogue_text, sota_analysis
            )
            final_feedback_parts.append(f"\n🎯 Expert Dialogue Assessment:\n{llm_feedback}")
        except Exception as e:
            logger.error(f"Error in LLM assessment: {e}")
            is_qualitatively_realistic = False
            llm_feedback = "LLM assessment failed"
            dimensional_scores = {'overall': 2.0}
            final_feedback_parts.append(f"\n🎯 Expert Dialogue Assessment: ERROR - {llm_feedback}")

        # 5. REALISTIC decision logic with balanced weights
        weights = {
            'expert_assessment': 0.4,    # Expert judgment
            'safety_critical': 0.4,      # Safety is critical
            'sota_metrics': 0.2          # Supporting metrics
        }

        # Expert component
        expert_component = weights['expert_assessment'] if is_qualitatively_realistic else 0.0
        if dimensional_scores.get('overall', 0) > 0:
            expert_component *= min(1.0, dimensional_scores.get('overall', 3.0) / 4.0)

        # Safety component
        safety_score = sota_analysis.get('medical_safety', 0.0)
        safety_component = safety_score * weights['safety_critical']

        # SOTA metrics component
        key_sota_score = (
            sota_analysis.get('semantic_quality', 0.0) * 0.5 +
            sota_analysis.get('medical_coverage', 0.0) * 0.5
        )
        sota_component = key_sota_score * weights['sota_metrics']

        combined_score = expert_component + safety_component + sota_component

        # REALISTIC threshold
        threshold = self.sota_realism_threshold

        # Final decision with safety priority
        if safety_score < 0.5:
            # Safety override
            label = "unrealistic"
            decision_rationale = f"❌ UNREALISTIC - Safety concerns (Safety: {safety_score:.3f})"
        elif is_qualitatively_realistic and safety_score > 0.6:
            # Expert + safety confirmation
            label = "realistic"
            decision_rationale = f"✅ REALISTIC - Expert confirmed with good safety (Safety: {safety_score:.3f})"
        elif combined_score >= threshold:
            label = "realistic"
            decision_rationale = f"✅ REALISTIC (Score: {combined_score:.3f} ≥ {threshold:.3f})"
        else:
            label = "unrealistic"
            decision_rationale = f"❌ UNREALISTIC (Score: {combined_score:.3f} < {threshold:.3f})"

        # Realistic decision breakdown
        decision_breakdown = (
            f"{decision_rationale}\n"
            f"📈 Realistic Score Breakdown:\n"
            f"  • Expert Assessment: {expert_component:.3f}/{weights['expert_assessment']} "
            f"({'Realistic' if is_qualitatively_realistic else 'Unrealistic'})\n"
            f"  • Safety Evaluation: {safety_component:.3f}/{weights['safety_critical']} "
            f"(Score: {safety_score:.3f})\n"
            f"  • SOTA Metrics: {sota_component:.3f}/{weights['sota_metrics']} "
            f"(Combined: {key_sota_score:.3f})\n"
            f"🎯 Threshold: {threshold:.3f}"
        )

        final_feedback_parts.append(f"\n📋 Realistic Decision Analysis:\n{decision_breakdown}")
        
        logger.info(f"[Realistic Coach] Final assessment - Label: {label}, Score: {combined_score:.3f}, "
                   f"Expert: {is_qualitatively_realistic}, Safety: {safety_score:.3f}")
        
        return label, "\n\n".join(final_feedback_parts)

    def _create_realistic_sota_summary(self, sota_evaluation: dict, sota_analysis: Dict[str, float]) -> str:
        """Create realistic SOTA metrics summary"""
        
        summary = sota_evaluation.get('evaluation_summary', {})
        
        sota_summary = (
            f"📊 Realistic SOTA Evaluation Results:\n"
            f"Overall SOTA Score: {sota_evaluation.get('overall_sota_score', 0):.3f}\n"
            f"Safety Status: {summary.get('safety_status', 'UNKNOWN')}\n\n"
            
            f"🔬 Key Realistic Metrics:\n"
            f"• Medical Safety: {sota_analysis['medical_safety']:.3f} "
            f"{'✅' if sota_analysis['medical_safety'] > 0.6 else '❌'} (Critical)\n"
            f"• Semantic Quality: {sota_analysis['semantic_quality']:.3f} "
            f"{'✅' if sota_analysis['semantic_quality'] > 0.4 else '○'}\n"
            f"• Medical Coverage: {sota_analysis['medical_coverage']:.3f} "
            f"{'✅' if sota_analysis['medical_coverage'] > 0.4 else '○'}\n"
            f"• Dialogue Naturalness: {sota_analysis['dialogue_naturalness']:.3f} "
            f"{'✅' if sota_analysis['dialogue_naturalness'] > 0.4 else '○'}\n\n"
            
            f"🎯 Evaluation Notes:\n"
            f"• Expert assessment balanced with automated metrics\n"
            f"• Medical safety is the critical factor\n"
            f"• Realistic thresholds applied\n"
            f"• Focus on overall clinical authenticity"
        )
        
        return sota_summary

    def generate_feedback(self, dialogue_text: str, ground_truth: dict) -> str:
        """Generate realistic feedback for dialogue improvement"""
        _, feedback = self.review_dialogue(dialogue_text, ground_truth)
        return feedback