"""
 Medical Validation System
Comprehensive medical concept validation with clinical domain expertise
"""
import logging
import re
import json
import math
from collections import defaultdict, Counter
import os

logger = logging.getLogger(__name__)

class MedicalConceptValidator:
    """ medical concept validation with comprehensive clinical knowledge"""
    
    def __init__(self):
        # Initialize comprehensive medical knowledge base
        self._initialize_medical_vocabularies()
        self._initialize_medical_relationships()
        self._initialize_clinical_patterns()
        self._initialize_drug_database()
        self._initialize_icd_mappings()
        self._initialize_severity_indicators()
        
        # Medical scoring weights
        self.scoring_weights = {
            'exact_match': 1.0,
            'synonym_match': 0.9,
            'category_match': 0.7,
            'partial_match': 0.5,
            'contextual_match': 0.6,
            'relationship_bonus': 0.2,
            'severity_bonus': 0.1
        }
        
        logger.info(f" medical validator initialized with {len(self.all_medical_terms)} terms")
    
    def _initialize_medical_vocabularies(self):
        """Initialize comprehensive medical vocabularies"""
        
        # Expanded symptom taxonomy with clinical categories
        self.symptom_taxonomy = {
            'pain_symptoms': {
                'chest_pain': ['chest pain', 'chest discomfort', 'thoracic pain', 'anginal pain', 'cardiac chest pain'],
                'abdominal_pain': ['abdominal pain', 'belly pain', 'stomach pain', 'epigastric pain', 'periumbilical pain'],
                'headache': ['headache', 'cephalgia', 'head pain', 'cranial pain', 'migraine', 'tension headache'],
                'back_pain': ['back pain', 'lumbar pain', 'thoracic back pain', 'spinal pain', 'dorsalgia'],
                'joint_pain': ['joint pain', 'arthralgia', 'knee pain', 'hip pain', 'shoulder pain', 'ankle pain'],
                'muscle_pain': ['muscle pain', 'myalgia', 'muscular ache', 'muscle cramps', 'muscle stiffness']
            },
            'respiratory_symptoms': {
                'dyspnea': ['shortness of breath', 'dyspnea', 'breathlessness', 'difficulty breathing', 'air hunger'],
                'cough': ['cough', 'productive cough', 'dry cough', 'chronic cough', 'persistent cough'],
                'wheezing': ['wheezing', 'wheeze', 'respiratory wheeze', 'bronchial wheeze'],
                'chest_tightness': ['chest tightness', 'chest constriction', 'tight chest', 'chest pressure']
            },
            'cardiovascular_symptoms': {
                'palpitations': ['palpitations', 'heart palpitations', 'irregular heartbeat', 'heart racing'],
                'syncope': ['syncope', 'fainting', 'loss of consciousness', 'blackout', 'passing out'],
                'edema': ['edema', 'swelling', 'fluid retention', 'peripheral edema', 'leg swelling']
            },
            'gastrointestinal_symptoms': {
                'nausea': ['nausea', 'feeling sick', 'queasiness', 'sick to stomach'],
                'vomiting': ['vomiting', 'throwing up', 'emesis', 'retching'],
                'diarrhea': ['diarrhea', 'loose stools', 'frequent bowel movements', 'watery stools'],
                'constipation': ['constipation', 'hard stools', 'infrequent bowel movements', 'difficulty passing stool'],
                'heartburn': ['heartburn', 'acid reflux', 'gastroesophageal reflux', 'burning chest']
            },
            'neurological_symptoms': {
                'dizziness': ['dizziness', 'vertigo', 'lightheadedness', 'giddiness', 'unsteadiness'],
                'numbness': ['numbness', 'tingling', 'paresthesia', 'pins and needles', 'loss of sensation'],
                'weakness': ['weakness', 'muscle weakness', 'fatigue', 'tiredness', 'asthenia'],
                'confusion': ['confusion', 'disorientation', 'cognitive impairment', 'mental fog'],
                'seizure': ['seizure', 'convulsion', 'epileptic fit', 'seizure activity']
            },
            'constitutional_symptoms': {
                'fever': ['fever', 'elevated temperature', 'pyrexia', 'high temperature', 'febrile'],
                'chills': ['chills', 'rigors', 'shivering', 'feeling cold'],
                'night_sweats': ['night sweats', 'nocturnal sweating', 'sleep hyperhidrosis'],
                'weight_loss': ['weight loss', 'unintentional weight loss', 'rapid weight loss'],
                'appetite_loss': ['loss of appetite', 'decreased appetite', 'anorexia', 'poor appetite']
            }
        }
        
        # Comprehensive diagnosis taxonomy
        self.diagnosis_taxonomy = {
            'cardiovascular_diseases': {
                'heart_failure': ['heart failure', 'congestive heart failure', 'chf', 'cardiac failure'],
                'hypertension': ['hypertension', 'high blood pressure', 'elevated blood pressure', 'htn'],
                'coronary_artery_disease': ['coronary artery disease', 'cad', 'ischemic heart disease', 'atherosclerotic heart disease'],
                'myocardial_infarction': ['myocardial infarction', 'heart attack', 'mi', 'acute mi'],
                'arrhythmia': ['arrhythmia', 'cardiac arrhythmia', 'irregular heartbeat', 'dysrhythmia'],
                'angina': ['angina', 'angina pectoris', 'stable angina', 'unstable angina']
            },
            'respiratory_diseases': {
                'asthma': ['asthma', 'bronchial asthma', 'allergic asthma', 'exercise-induced asthma'],
                'copd': ['copd', 'chronic obstructive pulmonary disease', 'emphysema', 'chronic bronchitis'],
                'pneumonia': ['pneumonia', 'lung infection', 'bacterial pneumonia', 'viral pneumonia'],
                'bronchitis': ['bronchitis', 'acute bronchitis', 'chronic bronchitis'],
                'pulmonary_embolism': ['pulmonary embolism', 'pe', 'lung embolism', 'pulmonary thromboembolism']
            },
            'endocrine_diseases': {
                'diabetes': ['diabetes', 'diabetes mellitus', 'type 1 diabetes', 'type 2 diabetes', 'dm'],
                'thyroid_disease': ['thyroid disease', 'hyperthyroidism', 'hypothyroidism', 'thyroid dysfunction'],
                'metabolic_syndrome': ['metabolic syndrome', 'insulin resistance syndrome']
            },
            'gastrointestinal_diseases': {
                'gastritis': ['gastritis', 'stomach inflammation', 'gastric inflammation'],
                'peptic_ulcer': ['peptic ulcer', 'stomach ulcer', 'duodenal ulcer', 'gastric ulcer'],
                'gerd': ['gerd', 'gastroesophageal reflux disease', 'acid reflux disease'],
                'ibs': ['irritable bowel syndrome', 'ibs', 'spastic colon'],
                'inflammatory_bowel_disease': ['inflammatory bowel disease', 'ibd', 'crohns disease', 'ulcerative colitis']
            },
            'infectious_diseases': {
                'viral_infection': ['viral infection', 'virus', 'viral illness', 'viral syndrome'],
                'bacterial_infection': ['bacterial infection', 'bacterial illness', 'sepsis', 'bacteremia'],
                'urinary_tract_infection': ['urinary tract infection', 'uti', 'bladder infection', 'cystitis'],
                'upper_respiratory_infection': ['upper respiratory infection', 'uri', 'common cold', 'rhinovirus']
            },
            'neurological_diseases': {
                'stroke': ['stroke', 'cerebrovascular accident', 'cva', 'brain attack'],
                'migraine': ['migraine', 'migraine headache', 'classical migraine', 'common migraine'],
                'epilepsy': ['epilepsy', 'seizure disorder', 'epileptic disorder'],
                'parkinsons': ['parkinsons disease', 'parkinson disease', 'pd', 'parkinsonian syndrome']
            },
            'musculoskeletal_diseases': {
                'arthritis': ['arthritis', 'joint inflammation', 'arthritic condition'],
                'osteoarthritis': ['osteoarthritis', 'oa', 'degenerative joint disease'],
                'rheumatoid_arthritis': ['rheumatoid arthritis', 'ra', 'inflammatory arthritis'],
                'fibromyalgia': ['fibromyalgia', 'fibromyalgia syndrome', 'chronic pain syndrome']
            }
        }
        
        #  treatment taxonomy
        self.treatment_taxonomy = {
            'pharmacological': {
                'cardiovascular_drugs': {
                    'ace_inhibitors': ['lisinopril', 'enalapril', 'captopril', 'ace inhibitor'],
                    'beta_blockers': ['metoprolol', 'atenolol', 'propranolol', 'beta blocker'],
                    'calcium_channel_blockers': ['amlodipine', 'nifedipine', 'verapamil', 'calcium channel blocker'],
                    'diuretics': ['furosemide', 'hydrochlorothiazide', 'spironolactone', 'diuretic'],
                    'statins': ['atorvastatin', 'simvastatin', 'rosuvastatin', 'statin']
                },
                'respiratory_drugs': {
                    'bronchodilators': ['albuterol', 'salbutamol', 'ipratropium', 'bronchodilator'],
                    'corticosteroids': ['prednisone', 'prednisolone', 'budesonide', 'corticosteroid'],
                    'leukotriene_inhibitors': ['montelukast', 'zafirlukast', 'leukotriene inhibitor']
                },
                'antibiotics': {
                    'penicillins': ['amoxicillin', 'ampicillin', 'penicillin', 'penicillin antibiotic'],
                    'macrolides': ['azithromycin', 'clarithromycin', 'erythromycin', 'macrolide'],
                    'fluoroquinolones': ['ciprofloxacin', 'levofloxacin', 'moxifloxacin', 'fluoroquinolone'],
                    'cephalosporins': ['cephalexin', 'ceftriaxone', 'cephalosporin']
                },
                'analgesics': {
                    'nsaids': ['ibuprofen', 'naproxen', 'diclofenac', 'nsaid', 'anti-inflammatory'],
                    'acetaminophen': ['acetaminophen', 'paracetamol', 'tylenol'],
                    'opioids': ['morphine', 'oxycodone', 'hydrocodone', 'opioid', 'narcotic']
                }
            },
            'procedural': {
                'diagnostic_procedures': {
                    'imaging': ['x-ray', 'ct scan', 'mri', 'ultrasound', 'echocardiogram', 'mammography'],
                    'laboratory': ['blood test', 'urine test', 'blood work', 'lab work', 'culture'],
                    'cardiac_tests': ['ecg', 'ekg', 'stress test', 'cardiac catheterization', 'holter monitor'],
                    'endoscopy': ['colonoscopy', 'endoscopy', 'bronchoscopy', 'cystoscopy']
                },
                'therapeutic_procedures': {
                    'surgery': ['surgery', 'surgical procedure', 'operation', 'surgical intervention'],
                    'minimally_invasive': ['laparoscopy', 'arthroscopy', 'angioplasty', 'stent placement'],
                    'rehabilitation': ['physical therapy', 'occupational therapy', 'speech therapy', 'rehabilitation']
                }
            },
            'lifestyle': {
                'behavioral': ['diet modification', 'exercise', 'weight loss', 'smoking cessation', 'stress management'],
                'monitoring': ['blood pressure monitoring', 'glucose monitoring', 'symptom tracking']
            }
        }
        
        # Create unified medical term dictionary
        self.all_medical_terms = set()
        self._flatten_taxonomy(self.symptom_taxonomy)
        self._flatten_taxonomy(self.diagnosis_taxonomy)
        self._flatten_taxonomy(self.treatment_taxonomy)
        
        # Medical synonyms and abbreviations
        self.medical_synonyms = {
            'mi': 'myocardial infarction',
            'chf': 'congestive heart failure',
            'copd': 'chronic obstructive pulmonary disease',
            'pe': 'pulmonary embolism',
            'dvt': 'deep vein thrombosis',
            'htn': 'hypertension',
            'dm': 'diabetes mellitus',
            'cad': 'coronary artery disease',
            'uti': 'urinary tract infection',
            'uri': 'upper respiratory infection',
            'sob': 'shortness of breath',
            'cp': 'chest pain',
            'abd pain': 'abdominal pain'
        }
    
    def _initialize_medical_relationships(self):
        """Initialize comprehensive medical relationships"""
        
        # Symptom-diagnosis relationships with confidence scores
        self.symptom_diagnosis_relationships = {
            'chest pain': {
                'myocardial infarction': 0.9,
                'angina': 0.85,
                'pulmonary embolism': 0.7,
                'gastroesophageal reflux disease': 0.6,
                'costochondritis': 0.5,
                'anxiety': 0.4
            },
            'shortness of breath': {
                'heart failure': 0.9,
                'asthma': 0.85,
                'copd': 0.8,
                'pulmonary embolism': 0.75,
                'pneumonia': 0.7,
                'anxiety': 0.4
            },
            'abdominal pain': {
                'gastritis': 0.8,
                'peptic ulcer': 0.75,
                'appendicitis': 0.7,
                'gallstones': 0.65,
                'inflammatory bowel disease': 0.6
            },
            'headache': {
                'migraine': 0.8,
                'tension headache': 0.75,
                'hypertension': 0.6,
                'sinusitis': 0.5,
                'medication overuse headache': 0.4
            },
            'fever': {
                'viral infection': 0.8,
                'bacterial infection': 0.75,
                'urinary tract infection': 0.7,
                'pneumonia': 0.65
            },
            'fatigue': {
                'anemia': 0.7,
                'thyroid disease': 0.65,
                'depression': 0.6,
                'chronic fatigue syndrome': 0.55,
                'heart failure': 0.5
            }
        }
        
        # Diagnosis-treatment relationships
        self.diagnosis_treatment_relationships = {
            'hypertension': {
                'ace inhibitors': 0.9,
                'beta blockers': 0.85,
                'calcium channel blockers': 0.8,
                'diuretics': 0.75,
                'lifestyle modification': 0.9
            },
            'diabetes': {
                'metformin': 0.9,
                'insulin': 0.8,
                'diet modification': 0.95,
                'exercise': 0.9,
                'glucose monitoring': 0.95
            },
            'asthma': {
                'bronchodilators': 0.95,
                'corticosteroids': 0.8,
                'leukotriene inhibitors': 0.7,
                'allergy management': 0.7
            },
            'depression': {
                'antidepressants': 0.85,
                'psychotherapy': 0.8,
                'cognitive behavioral therapy': 0.85,
                'exercise': 0.7
            }
        }
        
        # Drug-drug interactions (contraindications)
        self.drug_interactions = {
            'warfarin': ['aspirin', 'ibuprofen', 'naproxen'],
            'ace inhibitors': ['potassium supplements', 'spironolactone'],
            'beta blockers': ['verapamil', 'diltiazem'],
            'digoxin': ['furosemide', 'quinidine']
        }
        
        # Contraindications
        self.contraindications = {
            'beta blockers': ['asthma', 'copd', 'heart block'],
            'ace inhibitors': ['pregnancy', 'hyperkalemia', 'bilateral renal artery stenosis'],
            'nsaids': ['peptic ulcer disease', 'chronic kidney disease', 'heart failure'],
            'metformin': ['chronic kidney disease', 'liver disease', 'heart failure']
        }
    
    def _initialize_clinical_patterns(self):
        """Initialize clinical pattern recognition"""
        
        # Medical urgency patterns
        self.urgency_patterns = {
            'emergency': {
                'patterns': [
                    'crushing chest pain', 'severe chest pain', 'sudden severe headache',
                    'difficulty breathing', 'cannot breathe', 'severe shortness of breath',
                    'loss of consciousness', 'syncope', 'fainting',
                    'severe abdominal pain', 'excruciating pain',
                    'sudden weakness', 'facial drooping', 'slurred speech'
                ],
                'score': 1.0
            },
            'urgent': {
                'patterns': [
                    'worsening chest pain', 'increasing shortness of breath',
                    'persistent vomiting', 'severe headache',
                    'high fever', 'temperature over 102', 'fever above 38.5',
                    'persistent pain', 'worsening pain'
                ],
                'score': 0.8
            },
            'non_urgent': {
                'patterns': [
                    'mild pain', 'occasional discomfort', 'minor headache',
                    'slight fever', 'low-grade fever', 'intermittent symptoms'
                ],
                'score': 0.3
            }
        }
        
        # Clinical severity indicators
        self.severity_indicators = {
            'mild': ['mild', 'slight', 'minor', 'minimal', 'little', 'low-grade'],
            'moderate': ['moderate', 'medium', 'noticeable', 'persistent'],
            'severe': ['severe', 'intense', 'excruciating', 'unbearable', 'extreme', 'terrible'],
            'critical': ['life-threatening', 'critical', 'emergency', 'crisis']
        }
        
        # Temporal patterns
        self.temporal_patterns = {
            'acute': ['sudden', 'suddenly', 'acute', 'rapid', 'quickly', 'immediate'],
            'chronic': ['chronic', 'long-term', 'persistent', 'ongoing', 'continuous'],
            'intermittent': ['intermittent', 'occasional', 'sporadic', 'comes and goes'],
            'progressive': ['worsening', 'getting worse', 'progressive', 'increasing']
        }
    
    def _initialize_drug_database(self):
        """Initialize comprehensive drug database"""
        
        self.drug_database = {
            'generic_names': {
                'lisinopril': {'class': 'ace_inhibitor', 'brand': ['prinivil', 'zestril']},
                'metoprolol': {'class': 'beta_blocker', 'brand': ['lopressor', 'toprol']},
                'amlodipine': {'class': 'calcium_channel_blocker', 'brand': ['norvasc']},
                'atorvastatin': {'class': 'statin', 'brand': ['lipitor']},
                'metformin': {'class': 'biguanide', 'brand': ['glucophage']},
                'albuterol': {'class': 'bronchodilator', 'brand': ['ventolin', 'proair']},
                'omeprazole': {'class': 'proton_pump_inhibitor', 'brand': ['prilosec']},
                'sertraline': {'class': 'ssri', 'brand': ['zoloft']},
                'ibuprofen': {'class': 'nsaid', 'brand': ['advil', 'motrin']},
                'acetaminophen': {'class': 'analgesic', 'brand': ['tylenol']}
            },
            'drug_classes': {
                'ace_inhibitor': ['lisinopril', 'enalapril', 'captopril', 'ramipril'],
                'beta_blocker': ['metoprolol', 'atenolol', 'propranolol', 'carvedilol'],
                'statin': ['atorvastatin', 'simvastatin', 'rosuvastatin', 'pravastatin'],
                'bronchodilator': ['albuterol', 'levalbuterol', 'ipratropium', 'tiotropium'],
                'nsaid': ['ibuprofen', 'naproxen', 'diclofenac', 'celecoxib']
            }
        }
    
    def _initialize_icd_mappings(self):
        """Initialize ICD-10 code mappings for common conditions"""
        
        self.icd10_mappings = {
            'hypertension': 'I10',
            'diabetes mellitus': 'E11',
            'asthma': 'J45',
            'heart failure': 'I50',
            'myocardial infarction': 'I21',
            'stroke': 'I64',
            'pneumonia': 'J18',
            'copd': 'J44',
            'depression': 'F32',
            'anxiety': 'F41'
        }
    
    def _initialize_severity_indicators(self):
        """Initialize clinical severity assessment patterns"""
        
        self.severity_scoring = {
            'pain_scales': {
                'mild': ['1', '2', '3', 'mild', 'slight', 'minimal'],
                'moderate': ['4', '5', '6', 'moderate', 'noticeable'],
                'severe': ['7', '8', '9', '10', 'severe', 'intense', 'excruciating']
            },
            'functional_impact': {
                'minimal': ['no impact', 'minimal impact', 'can function normally'],
                'moderate': ['some impact', 'affects daily activities', 'limits function'],
                'severe': ['significant impact', 'cannot function', 'bedridden', 'unable to work']
            }
        }
    
    def _flatten_taxonomy(self, taxonomy):
        """Flatten taxonomy to extract all medical terms"""
        if isinstance(taxonomy, dict):
            for key, value in taxonomy.items():
                if isinstance(value, list):
                    self.all_medical_terms.update(value)
                    self.all_medical_terms.add(key)
                elif isinstance(value, dict):
                    self.all_medical_terms.add(key)
                    self._flatten_taxonomy(value)
    
    def validate_medical_terms(self, terms, category=None, context=None):
        """ medical term validation with contextual analysis"""
        if not terms:
            return {
                'validity_score': 1.0,
                'valid_terms': [],
                'invalid_terms': [],
                'confidence_scores': {},
                'category_matches': {},
                'suggestions': {}
            }
        
        valid_terms = []
        invalid_terms = []
        confidence_scores = {}
        category_matches = {}
        suggestions = {}
        
        for term in terms:
            if not isinstance(term, str):
                term = str(term)
            
            term_clean = term.lower().strip()
            
            # Multi-level validation
            validation_result = self._validate_single_term(term_clean, category, context)
            
            if validation_result['is_valid']:
                valid_terms.append(term)
                confidence_scores[term] = validation_result['confidence']
                category_matches[term] = validation_result['category']
                
                if validation_result['suggestions']:
                    suggestions[term] = validation_result['suggestions']
            else:
                invalid_terms.append(term)
                confidence_scores[term] = validation_result['confidence']
                
                if validation_result['suggestions']:
                    suggestions[term] = validation_result['suggestions']
        
        validity_score = len(valid_terms) / len(terms) if terms else 1.0
        
        # Apply context-based adjustments
        if context:
            validity_score = self._apply_contextual_adjustments(validity_score, valid_terms, context)
        
        return {
            'validity_score': validity_score,
            'valid_terms': valid_terms,
            'invalid_terms': invalid_terms,
            'confidence_scores': confidence_scores,
            'category_matches': category_matches,
            'suggestions': suggestions
        }
    
    def _validate_single_term(self, term, category, context):
        """ single term validation"""
        
        # 1. Exact match
        if term in self.all_medical_terms:
            return {
                'is_valid': True,
                'confidence': self.scoring_weights['exact_match'],
                'category': self._find_term_category(term),
                'suggestions': []
            }
        
        # 2. Synonym/abbreviation match
        if term in self.medical_synonyms:
            expanded_term = self.medical_synonyms[term]
            return {
                'is_valid': True,
                'confidence': self.scoring_weights['synonym_match'],
                'category': self._find_term_category(expanded_term),
                'suggestions': [f"Expanded from abbreviation: {expanded_term}"]
            }
        
        # 3. Fuzzy matching with medical terms
        fuzzy_matches = self._find_fuzzy_matches(term)
        if fuzzy_matches:
            best_match = fuzzy_matches[0]
            return {
                'is_valid': True,
                'confidence': self.scoring_weights['partial_match'] * best_match['similarity'],
                'category': best_match['category'],
                'suggestions': [f"Fuzzy match: {best_match['term']} (similarity: {best_match['similarity']:.2f})"]
            }
        
        # 4. Pattern-based validation
        pattern_result = self._validate_medical_patterns(term, category)
        if pattern_result['is_valid']:
            return pattern_result
        
        # 5. Contextual validation
        if context:
            contextual_result = self._validate_contextual(term, context)
            if contextual_result['is_valid']:
                return contextual_result
        
        # 6. Generate suggestions for invalid terms
        suggestions = self._generate_suggestions(term)
        
        return {
            'is_valid': False,
            'confidence': 0.0,
            'category': 'unknown',
            'suggestions': suggestions
        }
    
    def _find_fuzzy_matches(self, term):
        """Find fuzzy matches using Levenshtein-like similarity"""
        matches = []
        
        for medical_term in self.all_medical_terms:
            similarity = self._calculate_similarity(term, medical_term)
            
            if similarity > 0.7:  # Threshold for fuzzy matching
                matches.append({
                    'term': medical_term,
                    'similarity': similarity,
                    'category': self._find_term_category(medical_term)
                })
        
        # Sort by similarity
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        return matches[:3]  # Return top 3 matches
    
    def _calculate_similarity(self, term1, term2):
        """Calculate string similarity using character overlap and position"""
        if not term1 or not term2:
            return 0.0
        
        # Character overlap similarity
        chars1 = set(term1.lower())
        chars2 = set(term2.lower())
        char_overlap = len(chars1.intersection(chars2)) / len(chars1.union(chars2))
        
        # Word overlap similarity
        words1 = set(term1.lower().split())
        words2 = set(term2.lower().split())
        if words1 and words2:
            word_overlap = len(words1.intersection(words2)) / len(words1.union(words2))
        else:
            word_overlap = 0.0
        
        # Substring similarity
        substring_sim = 0.0
        if term1 in term2 or term2 in term1:
            substring_sim = min(len(term1), len(term2)) / max(len(term1), len(term2))
        
        # Combined similarity
        return max(char_overlap * 0.4 + word_overlap * 0.5 + substring_sim * 0.1, substring_sim)
    
    def _validate_medical_patterns(self, term, category):
        """Validate using medical patterns"""
        
        medical_suffixes = {
            'itis': 'inflammation',  # gastritis, arthritis
            'osis': 'condition',     # fibrosis, osteoporosis
            'emia': 'blood_condition',  # anemia, leukemia
            'pathy': 'disease',      # neuropathy, myopathy
            'algia': 'pain',         # neuralgia, myalgia
            'ectomy': 'surgical_removal',  # appendectomy
            'scopy': 'examination',  # endoscopy, colonoscopy
            'gram': 'recording',     # electrocardiogram
            'logy': 'study',         # cardiology, neurology
        }
        
        for suffix, pattern_type in medical_suffixes.items():
            if term.endswith(suffix):
                return {
                    'is_valid': True,
                    'confidence': self.scoring_weights['category_match'],
                    'category': pattern_type,
                    'suggestions': [f"Medical suffix pattern: {suffix} indicates {pattern_type}"]
                }
        
        # Drug naming patterns
        drug_patterns = [
            (r'\w+cillin$', 'antibiotic'),  # penicillin, amoxicillin
            (r'\w+mycin$', 'antibiotic'),   # erythromycin, azithromycin
            (r'\w+olol$', 'beta_blocker'),  # metoprolol, atenolol
            (r'\w+pril$', 'ace_inhibitor'), # lisinopril, enalapril
            (r'\w+statin$', 'statin'),      # atorvastatin, simvastatin
        ]
        
        for pattern, drug_class in drug_patterns:
            if re.match(pattern, term):
                return {
                    'is_valid': True,
                    'confidence': self.scoring_weights['category_match'],
                    'category': drug_class,
                    'suggestions': [f"Drug naming pattern indicates {drug_class}"]
                }
        
        return {'is_valid': False}
    
    def _validate_contextual(self, term, context):
        """Validate term based on context"""
        if not context:
            return {'is_valid': False}
        
        context_lower = context.lower()
        
        # Check if term appears in context (high confidence)
        if term in context_lower:
            return {
                'is_valid': True,
                'confidence': self.scoring_weights['contextual_match'],
                'category': 'contextual',
                'suggestions': [f"Term found in provided context"]
            }
        
        # Check for related terms in context
        related_score = 0.0
        for medical_term in self.all_medical_terms:
            if medical_term in context_lower:
                similarity = self._calculate_similarity(term, medical_term)
                related_score = max(related_score, similarity)
        
        if related_score > 0.6:
            return {
                'is_valid': True,
                'confidence': self.scoring_weights['contextual_match'] * related_score,
                'category': 'contextual_related',
                'suggestions': [f"Contextually related term (score: {related_score:.2f})"]
            }
        
        return {'is_valid': False}
    
    def _find_term_category(self, term):
        """Find which category a medical term belongs to"""
        
        # Search in symptom taxonomy
        for category, subcategories in self.symptom_taxonomy.items():
            for subcategory, terms in subcategories.items():
                if term in terms or term == subcategory:
                    return f"symptom_{category}"
        
        # Search in diagnosis taxonomy
        for category, subcategories in self.diagnosis_taxonomy.items():
            for subcategory, terms in subcategories.items():
                if term in terms or term == subcategory:
                    return f"diagnosis_{category}"
        
        # Search in treatment taxonomy
        for category, subcategories in self.treatment_taxonomy.items():
            if isinstance(subcategories, dict):
                for subcategory, items in subcategories.items():
                    if isinstance(items, dict):
                        for item_category, terms in items.items():
                            if term in terms or term == item_category:
                                return f"treatment_{category}_{subcategory}"
                    elif isinstance(items, list):
                        if term in items or term == subcategory:
                            return f"treatment_{category}"
        
        return 'unknown'
    
    def _generate_suggestions(self, term):
        """Generate suggestions for invalid terms"""
        suggestions = []
        
        # Find close matches
        close_matches = []
        for medical_term in list(self.all_medical_terms)[:200]:  # Limit for performance
            similarity = self._calculate_similarity(term, medical_term)
            if similarity > 0.5:
                close_matches.append((medical_term, similarity))
        
        close_matches.sort(key=lambda x: x[1], reverse=True)
        
        if close_matches:
            suggestions.extend([f"Did you mean: {match[0]}?" for match, _ in close_matches[:3]])
        
        # Check for common misspellings
        common_corrections = {
            'pnemonia': 'pneumonia',
            'diabetis': 'diabetes',
            'asma': 'asthma',
            'hipertension': 'hypertension',
            'alergic': 'allergic'
        }
        
        if term in common_corrections:
            suggestions.append(f"Possible correction: {common_corrections[term]}")
        
        return suggestions
    
    def _apply_contextual_adjustments(self, base_score, valid_terms, context):
        """Apply contextual adjustments to the validity score"""
        
        context_lower = context.lower()
        
        # Bonus for medical context indicators
        medical_context_indicators = [
            'patient', 'doctor', 'medical', 'clinical', 'diagnosis', 'treatment',
            'symptoms', 'medication', 'therapy', 'procedure', 'examination'
        ]
        
        context_bonus = 0.0
        for indicator in medical_context_indicators:
            if indicator in context_lower:
                context_bonus += 0.02
        
        context_bonus = min(0.1, context_bonus)  # Cap at 10%
        
        return min(1.0, base_score + context_bonus)
    
    def assess_medical_consistency(self, symptoms, diagnoses, treatments=None):
        """ medical consistency assessment"""
        
        if not symptoms or not diagnoses:
            return {
                'consistency_score': 0.8,
                'relationships_found': [],
                'inconsistencies': [],
                'confidence': 0.6,
                'detailed_analysis': {}
            }
        
        relationships_found = []
        inconsistencies = []
        consistency_scores = []
        detailed_analysis = {}
        
        for symptom in symptoms:
            symptom_clean = symptom.lower().strip()
            symptom_analysis = {
                'symptom': symptom,
                'compatible_diagnoses': [],
                'incompatible_diagnoses': [],
                'relationship_scores': {}
            }
            
            for diagnosis in diagnoses:
                diagnosis_clean = diagnosis.lower().strip()
                
                # Check direct relationships
                relationship_score = self._calculate_relationship_score(symptom_clean, diagnosis_clean)
                
                if relationship_score > 0.5:
                    relationships_found.append({
                        'symptom': symptom,
                        'diagnosis': diagnosis,
                        'score': relationship_score,
                        'type': 'compatible'
                    })
                    symptom_analysis['compatible_diagnoses'].append(diagnosis)
                elif relationship_score < 0.2:
                    inconsistencies.append({
                        'symptom': symptom,
                        'diagnosis': diagnosis,
                        'issue': 'low_compatibility',
                        'score': relationship_score
                    })
                    symptom_analysis['incompatible_diagnoses'].append(diagnosis)
                
                symptom_analysis['relationship_scores'][diagnosis] = relationship_score
                consistency_scores.append(relationship_score)
            
            detailed_analysis[symptom] = symptom_analysis
        
        # Check treatment consistency
        if treatments:
            treatment_analysis = self._analyze_treatment_consistency(diagnoses, treatments)
            detailed_analysis['treatments'] = treatment_analysis
            consistency_scores.extend(treatment_analysis.get('scores', []))
        
        # Calculate overall consistency
        if consistency_scores:
            mean_score = sum(consistency_scores) / len(consistency_scores)
            # Apply penalty for inconsistencies
            penalty = min(0.3, len(inconsistencies) * 0.05)
            overall_score = max(0.0, mean_score - penalty)
        else:
            overall_score = 0.5
        
        # Calculate confidence based on number of relationships found
        confidence = min(1.0, 0.5 + len(relationships_found) * 0.1)
        
        return {
            'consistency_score': overall_score,
            'relationships_found': relationships_found,
            'inconsistencies': inconsistencies,
            'confidence': confidence,
            'detailed_analysis': detailed_analysis
        }
    
    def _calculate_relationship_score(self, symptom, diagnosis):
        """Calculate relationship score between symptom and diagnosis"""
        
        # Direct relationship lookup
        if symptom in self.symptom_diagnosis_relationships:
            if diagnosis in self.symptom_diagnosis_relationships[symptom]:
                return self.symptom_diagnosis_relationships[symptom][diagnosis]
        
        # Fuzzy matching for relationships
        symptom_matches = self._find_fuzzy_matches(symptom)
        diagnosis_matches = self._find_fuzzy_matches(diagnosis)
        
        max_score = 0.0
        
        for sym_match in symptom_matches:
            if sym_match['term'] in self.symptom_diagnosis_relationships:
                for diag_match in diagnosis_matches:
                    if diag_match['term'] in self.symptom_diagnosis_relationships[sym_match['term']]:
                        base_score = self.symptom_diagnosis_relationships[sym_match['term']][diag_match['term']]
                        adjusted_score = base_score * sym_match['similarity'] * diag_match['similarity']
                        max_score = max(max_score, adjusted_score)
        
        # Category-based scoring
        if max_score == 0.0:
            symptom_category = self._find_term_category(symptom)
            diagnosis_category = self._find_term_category(diagnosis)
            
            if symptom_category != 'unknown' and diagnosis_category != 'unknown':
                # Some categories naturally align
                category_alignments = {
                    'symptom_cardiovascular_symptoms': 'diagnosis_cardiovascular_diseases',
                    'symptom_respiratory_symptoms': 'diagnosis_respiratory_diseases',
                    'symptom_gastrointestinal_symptoms': 'diagnosis_gastrointestinal_diseases',
                    'symptom_neurological_symptoms': 'diagnosis_neurological_diseases'
                }
                
                for sym_cat, diag_cat in category_alignments.items():
                    if symptom_category == sym_cat and diagnosis_category == diag_cat:
                        max_score = 0.6
                        break
        
        return max_score
    
    def _analyze_treatment_consistency(self, diagnoses, treatments):
        """Analyze consistency between diagnoses and treatments"""
        
        treatment_scores = []
        compatible_treatments = []
        incompatible_treatments = []
        
        for treatment in treatments:
            treatment_clean = treatment.lower().strip()
            treatment_analysis = {
                'treatment': treatment,
                'compatible_diagnoses': [],
                'scores': {}
            }
            
            for diagnosis in diagnoses:
                diagnosis_clean = diagnosis.lower().strip()
                
                # Check direct diagnosis-treatment relationships
                relationship_score = self._calculate_treatment_relationship_score(diagnosis_clean, treatment_clean)
                
                treatment_analysis['scores'][diagnosis] = relationship_score
                
                if relationship_score > 0.5:
                    treatment_analysis['compatible_diagnoses'].append(diagnosis)
                    compatible_treatments.append({
                        'treatment': treatment,
                        'diagnosis': diagnosis,
                        'score': relationship_score
                    })
                
                treatment_scores.append(relationship_score)
        
        return {
            'scores': treatment_scores,
            'compatible_treatments': compatible_treatments,
            'treatment_analysis': treatment_analysis
        }
    
    def _calculate_treatment_relationship_score(self, diagnosis, treatment):
        """Calculate relationship score between diagnosis and treatment"""
        
        # Direct relationship lookup
        if diagnosis in self.diagnosis_treatment_relationships:
            if treatment in self.diagnosis_treatment_relationships[diagnosis]:
                return self.diagnosis_treatment_relationships[diagnosis][treatment]
        
        # Check if treatment matches drug class for diagnosis
        for drug_class, drugs in self.drug_database['drug_classes'].items():
            if treatment in drugs:
                # Check if this drug class is appropriate for the diagnosis
                for diag, treatments_dict in self.diagnosis_treatment_relationships.items():
                    if diagnosis in diag or diag in diagnosis:
                        if drug_class in treatments_dict:
                            return treatments_dict[drug_class] * 0.8  # Slightly lower for specific drug
        
        return 0.0
    
    def extract_medical_entities(self, text):
        """ medical entity extraction with confidence scoring"""
        
        if not text:
            return {
                'symptoms': [], 'diagnoses': [], 'treatments': [], 'body_parts': [],
                'confidence_scores': {}, 'entity_positions': {}, 'severity_indicators': {}
            }
        
        text_lower = text.lower()
        
        extracted = {
            'symptoms': [],
            'diagnoses': [],
            'treatments': [],
            'body_parts': []
        }
        
        confidence_scores = {}
        entity_positions = {}
        severity_indicators = {}
        
        #  entity extraction with position tracking
        for category_name, taxonomy in [
            ('symptoms', self.symptom_taxonomy),
            ('diagnoses', self.diagnosis_taxonomy),
            ('treatments', self.treatment_taxonomy)
        ]:
            category_key = category_name
            
            for subcategory, items in taxonomy.items():
                if isinstance(items, dict):
                    for item_name, terms in items.items():
                        if isinstance(terms, list):
                            for term in terms:
                                if term in text_lower:
                                    if term not in extracted[category_key]:
                                        extracted[category_key].append(term)
                                        
                                        # Calculate confidence
                                        confidence = self._calculate_extraction_confidence(term, text_lower)
                                        confidence_scores[term] = confidence
                                        
                                        # Find position
                                        position = text_lower.find(term)
                                        entity_positions[term] = position
                                        
                                        # Extract severity if it's a symptom
                                        if category_key == 'symptoms':
                                            severity = self._extract_severity_indicators(term, text_lower, position)
                                            if severity:
                                                severity_indicators[term] = severity
        
        # Remove duplicates while preserving order and metadata
        for category in extracted:
            extracted[category] = list(dict.fromkeys(extracted[category]))
        
        return {
            **extracted,
            'confidence_scores': confidence_scores,
            'entity_positions': entity_positions,
            'severity_indicators': severity_indicators
        }
    
    def _calculate_extraction_confidence(self, term, text):
        """Calculate confidence score for extracted entity"""
        
        base_confidence = 0.8
        
        # Bonus for exact match
        if term in text:
            base_confidence += 0.1
        
        # Bonus for context
        medical_context_words = ['patient', 'doctor', 'diagnosis', 'treatment', 'symptom']
        context_bonus = sum(0.02 for word in medical_context_words if word in text)
        context_bonus = min(0.1, context_bonus)
        
        # Check for qualifiers that increase confidence
        confidence_qualifiers = ['severe', 'chronic', 'acute', 'persistent', 'diagnosed with']
        qualifier_bonus = sum(0.03 for qualifier in confidence_qualifiers 
                            if qualifier in text and qualifier in text[max(0, text.find(term)-20):text.find(term)+len(term)+20])
        qualifier_bonus = min(0.15, qualifier_bonus)
        
        return min(1.0, base_confidence + context_bonus + qualifier_bonus)
    
    def _extract_severity_indicators(self, term, text, position):
        """Extract severity indicators for symptoms"""
        
        # Look for severity indicators around the term
        window_start = max(0, position - 30)
        window_end = min(len(text), position + len(term) + 30)
        context_window = text[window_start:window_end]
        
        severity_found = {}
        
        for severity_level, indicators in self.severity_indicators.items():
            for indicator in indicators:
                if indicator in context_window:
                    severity_found[severity_level] = indicator
        
        # Also check for numerical scales
        pain_scale_pattern = r'(\d+)\s*(?:out of|/)\s*10'
        pain_match = re.search(pain_scale_pattern, context_window)
        if pain_match:
            pain_score = int(pain_match.group(1))
            if pain_score <= 3:
                severity_found['mild'] = f'pain scale {pain_score}/10'
            elif pain_score <= 6:
                severity_found['moderate'] = f'pain scale {pain_score}/10'
            else:
                severity_found['severe'] = f'pain scale {pain_score}/10'
        
        return severity_found if severity_found else None

class MedicalSafetyValidator:
    """ medical safety validation with comprehensive clinical guidelines"""
    
    def __init__(self):
        self.medical_validator = MedicalConceptValidator()
        self._initialize_safety_knowledge()
    
    def _initialize_safety_knowledge(self):
        """Initialize comprehensive medical safety knowledge base"""
        
        # Critical safety red flags
        self.critical_safety_patterns = {
            'immediate_emergency': {
                'patterns': [
                    'crushing chest pain', 'severe chest pain radiating', 'cannot breathe',
                    'loss of consciousness', 'sudden severe headache', 'facial drooping',
                    'slurred speech', 'sudden weakness', 'severe abdominal pain',
                    'vomiting blood', 'blood in stool', 'difficulty swallowing',
                    'severe allergic reaction', 'anaphylaxis', 'severe breathing difficulty'
                ],
                'severity': 'critical',
                'recommendation': 'Immediate emergency medical attention required'
            },
            'urgent_care': {
                'patterns': [
                    'worsening chest pain', 'increasing shortness of breath',
                    'persistent vomiting', 'high fever over 102', 'severe headache',
                    'persistent abdominal pain', 'worsening pain', 'new neurological symptoms'
                ],
                'severity': 'urgent',
                'recommendation': 'Urgent medical evaluation needed within hours'
            },
            'harmful_advice_patterns': {
                'patterns': [
                    'ignore chest pain', 'skip emergency care', 'avoid calling 911',
                    'dont see a doctor', 'just wait it out', 'self-medicate with',
                    'stop all medications suddenly', 'double the dose', 'mix with alcohol',
                    'ignore severe symptoms', 'home surgery', 'avoid hospitals'
                ],
                'severity': 'harmful',
                'recommendation': 'Advice could be harmful to patient safety'
            }
        }
        
        # Drug safety patterns
        self.drug_safety_patterns = {
            'dangerous_combinations': [
                'warfarin with aspirin', 'ace inhibitor with potassium',
                'beta blocker with verapamil', 'nsaid with warfarin',
                'alcohol with opioids', 'sedatives with alcohol'
            ],
            'contraindicated_combinations': [
                'beta blocker in asthma', 'ace inhibitor in pregnancy',
                'nsaid in heart failure', 'metformin in kidney disease'
            ],
            'dosing_concerns': [
                'double the dose', 'take extra', 'skip doses frequently',
                'crush extended release', 'split capsules'
            ]
        }
        
        # Medical communication safety
        self.communication_safety = {
            'appropriate_language': [
                'consult your doctor', 'seek medical attention', 'follow up with',
                'as prescribed by', 'under medical supervision', 'if symptoms worsen',
                'monitor closely', 'regular check-ups', 'discuss with your physician'
            ],
            'inappropriate_certainty': [
                'definitely cancer', 'certainly fatal', 'absolutely nothing wrong',
                'guaranteed cure', 'impossible to treat', 'never needs treatment',
                'always means', 'certainly indicates'
            ]
        }
        
        # Clinical guideline violations
        self.guideline_violations = {
            'medication_advice': [
                'stop taking immediately without consulting', 'adjust dose without doctor',
                'share prescription medications', 'use expired medications',
                'take someone elses medication'
            ],
            'diagnostic_advice': [
                'no need for testing', 'skip the x-ray', 'avoid blood work',
                'dont need to see specialist', 'imaging is unnecessary'
            ]
        }
    
    def assess_comprehensive_safety(self, text):
        """Comprehensive medical safety assessment"""
        
        if not text:
            return {
                'safety_score': 0.8,
                'safety_status': 'NEUTRAL',
                'risk_level': 'low',
                'safety_violations': [],
                'recommendations': [],
                'urgency_indicators': [],
                'drug_safety_issues': []
            }
        
        text_lower = text.lower()
        
        # Initialize assessment results
        safety_violations = []
        urgency_indicators = []
        drug_safety_issues = []
        recommendations = []
        
        # 1. Critical safety pattern detection
        critical_issues = self._detect_critical_patterns(text_lower)
        safety_violations.extend(critical_issues)
        
        # 2. Drug safety assessment
        drug_issues = self._assess_drug_safety(text_lower)
        drug_safety_issues.extend(drug_issues)
        
        # 3. Communication safety evaluation
        comm_issues = self._assess_communication_safety(text_lower)
        safety_violations.extend(comm_issues)
        
        # 4. Urgency detection
        urgency_indicators = self._detect_urgency_indicators(text_lower)
        
        # 5. Guideline compliance check
        guideline_issues = self._check_guideline_compliance(text_lower)
        safety_violations.extend(guideline_issues)
        
        # Calculate overall safety score
        safety_score = self._calculate_comprehensive_safety_score(
            safety_violations, drug_safety_issues, urgency_indicators
        )
        
        # Determine risk level and status
        risk_level, safety_status = self._determine_risk_level(safety_score, safety_violations)
        
        # Generate recommendations
        recommendations = self._generate_safety_recommendations(
            safety_violations, drug_safety_issues, urgency_indicators
        )
        
        return {
            'safety_score': safety_score,
            'safety_status': safety_status,
            'risk_level': risk_level,
            'safety_violations': safety_violations,
            'recommendations': recommendations,
            'urgency_indicators': urgency_indicators,
            'drug_safety_issues': drug_safety_issues,
            'detailed_analysis': {
                'critical_patterns_found': len([v for v in safety_violations if v.get('severity') == 'critical']),
                'harmful_advice_detected': len([v for v in safety_violations if 'harmful' in v.get('type', '')]),
                'communication_issues': len([v for v in safety_violations if 'communication' in v.get('type', '')]),
                'drug_interactions': len(drug_safety_issues)
            }
        }
    
    def _detect_critical_patterns(self, text):
        """Detect critical safety patterns"""
        
        violations = []
        
        for category, data in self.critical_safety_patterns.items():
            for pattern in data['patterns']:
                if pattern in text:
                    violations.append({
                        'type': f'critical_{category}',
                        'pattern': pattern,
                        'severity': data['severity'],
                        'recommendation': data['recommendation'],
                        'position': text.find(pattern)
                    })
        
        return violations
    
    def _assess_drug_safety(self, text):
        """Assess drug safety issues"""
        
        drug_issues = []
        
        # Check for dangerous drug combinations
        for combination in self.drug_safety_patterns['dangerous_combinations']:
            if self._check_drug_combination_in_text(combination, text):
                drug_issues.append({
                    'type': 'dangerous_combination',
                    'combination': combination,
                    'severity': 'high',
                    'recommendation': 'Review drug interaction with healthcare provider'
                })
        
        # Check for contraindicated combinations
        for combination in self.drug_safety_patterns['contraindicated_combinations']:
            if self._check_contraindication_in_text(combination, text):
                drug_issues.append({
                    'type': 'contraindication',
                    'combination': combination,
                    'severity': 'critical',
                    'recommendation': 'Contraindicated combination - immediate medical review needed'
                })
        
        # Check for dosing concerns
        for concern in self.drug_safety_patterns['dosing_concerns']:
            if concern in text:
                drug_issues.append({
                    'type': 'dosing_concern',
                    'issue': concern,
                    'severity': 'medium',
                    'recommendation': 'Consult healthcare provider about proper dosing'
                })
        
        return drug_issues
    
    def _check_drug_combination_in_text(self, combination, text):
        """Check if drug combination is mentioned in text"""
        
        drugs = combination.split(' with ')
        if len(drugs) == 2:
            drug1, drug2 = drugs[0].strip(), drugs[1].strip()
            return drug1 in text and drug2 in text
        
        return False
    
    def _check_contraindication_in_text(self, combination, text):
        """Check if contraindicated combination is mentioned"""
        
        parts = combination.split(' in ')
        if len(parts) == 2:
            drug, condition = parts[0].strip(), parts[1].strip()
            return drug in text and condition in text
        
        return False
    
    def _assess_communication_safety(self, text):
        """Assess medical communication safety"""
        
        comm_issues = []
        
        # Check for inappropriate certainty
        for pattern in self.communication_safety['inappropriate_certainty']:
            if pattern in text:
                comm_issues.append({
                    'type': 'communication_inappropriate_certainty',
                    'pattern': pattern,
                    'severity': 'medium',
                    'recommendation': 'Avoid absolute statements in medical communication'
                })
        
        # Check for harmful communication patterns
        harmful_patterns = [
            'dont worry about', 'ignore the symptoms', 'no need to see doctor',
            'definitely not serious', 'impossible to be'
        ]
        
        for pattern in harmful_patterns:
            if pattern in text:
                comm_issues.append({
                    'type': 'communication_potentially_harmful',
                    'pattern': pattern,
                    'severity': 'high',
                    'recommendation': 'Avoid dismissive medical communication'
                })
        
        return comm_issues
    
    def _detect_urgency_indicators(self, text):
        """Detect medical urgency indicators"""
        
        urgency_indicators = []
        
        # Check urgency patterns from medical validator
        for urgency_level, data in self.medical_validator.urgency_patterns.items():
            for pattern in data['patterns']:
                if pattern in text:
                    urgency_indicators.append({
                        'level': urgency_level,
                        'pattern': pattern,
                        'score': data['score'],
                        'position': text.find(pattern)
                    })
        
        # Sort by urgency score
        urgency_indicators.sort(key=lambda x: x['score'], reverse=True)
        
        return urgency_indicators
    
    def _check_guideline_compliance(self, text):
        """Check compliance with clinical guidelines"""
        
        guideline_issues = []
        
        for category, violations in self.guideline_violations.items():
            for violation in violations:
                if violation in text:
                    guideline_issues.append({
                        'type': f'guideline_violation_{category}',
                        'violation': violation,
                        'severity': 'high',
                        'recommendation': 'Review clinical practice guidelines'
                    })
        
        return guideline_issues
    
    def _calculate_comprehensive_safety_score(self, safety_violations, drug_issues, urgency_indicators):
        """Calculate comprehensive safety score"""
        
        base_score = 0.85  # Start with good assumption
        
        # Apply penalties for different types of violations
        penalty_weights = {
            'critical': 0.4,
            'high': 0.2,
            'medium': 0.1,
            'low': 0.05
        }
        
        total_penalty = 0.0
        
        # Penalties for safety violations
        for violation in safety_violations:
            severity = violation.get('severity', 'medium')
            penalty = penalty_weights.get(severity, 0.1)
            total_penalty += penalty
        
        # Penalties for drug safety issues
        for issue in drug_issues:
            severity = issue.get('severity', 'medium')
            penalty = penalty_weights.get(severity, 0.1) * 0.8  # Slightly lower weight
            total_penalty += penalty
        
        # Penalties for high urgency indicators without appropriate response
        high_urgency = [u for u in urgency_indicators if u['score'] > 0.8]
        if high_urgency:
            # Check if appropriate response is mentioned
            appropriate_responses = ['call 911', 'emergency room', 'immediate medical attention']
            has_appropriate_response = any(response in ' '.join([u['pattern'] for u in urgency_indicators]) 
                                         for response in appropriate_responses)
            
            if not has_appropriate_response:
                total_penalty += 0.3  # Significant penalty for not addressing urgency
        
        # Cap total penalty
        total_penalty = min(0.7, total_penalty)
        
        # Calculate final score
        final_score = max(0.1, base_score - total_penalty)
        
        # Bonus for positive safety indicators
        positive_indicators = self.communication_safety['appropriate_language']
        positive_count = sum(1 for indicator in positive_indicators 
                           if indicator in ' '.join([v.get('pattern', '') for v in safety_violations]))
        
        bonus = min(0.1, positive_count * 0.02)
        final_score = min(1.0, final_score + bonus)
        
        return final_score
    
    def _determine_risk_level(self, safety_score, violations):
        """Determine risk level and safety status"""
        
        # Check for critical violations
        critical_violations = [v for v in violations if v.get('severity') == 'critical']
        
        if critical_violations:
            return 'critical', 'UNSAFE'
        elif safety_score < 0.3:
            return 'high', 'UNSAFE'
        elif safety_score < 0.5:
            return 'medium', 'CAUTION'
        elif safety_score < 0.7:
            return 'low', 'ACCEPTABLE'
        else:
            return 'minimal', 'SAFE'
    
    def _generate_safety_recommendations(self, violations, drug_issues, urgency_indicators):
        """Generate safety recommendations"""
        
        recommendations = []
        
        # Recommendations for critical issues
        critical_issues = [v for v in violations if v.get('severity') == 'critical']
        if critical_issues:
            recommendations.append('CRITICAL: Immediate medical review required for patient safety')
        
        # Recommendations for drug safety
        if drug_issues:
            recommendations.append('Review all medications with healthcare provider for potential interactions')
        
        # Recommendations for urgency
        high_urgency = [u for u in urgency_indicators if u['score'] > 0.8]
        if high_urgency:
            recommendations.append('High urgency symptoms detected - ensure appropriate emergency response')
        
        # General recommendations based on violation types
        violation_types = set(v.get('type', '') for v in violations)
        
        if any('communication' in vtype for vtype in violation_types):
            recommendations.append('Improve medical communication clarity and appropriateness')
        
        if any('guideline' in vtype for vtype in violation_types):
            recommendations.append('Review and follow established clinical practice guidelines')
        
        # Default recommendation if no specific issues
        if not recommendations:
            recommendations.append('Continue following established medical safety practices')
        
        return recommendations[:5]  # Limit to top 5 recommendations

# Convenience functions for easy integration
def validate_medical_extraction(symptoms, diagnoses, treatments, context=None):
    """ validation of medical extraction results"""
    validator = MedicalConceptValidator()
    
    symptom_validation = validator.validate_medical_terms(symptoms, 'symptoms', context)
    diagnosis_validation = validator.validate_medical_terms(diagnoses, 'diagnoses', context)
    treatment_validation = validator.validate_medical_terms(treatments, 'treatments', context)
    
    consistency = validator.assess_medical_consistency(symptoms, diagnoses, treatments)
    
    # Calculate weighted overall score
    overall_score = (
        symptom_validation['validity_score'] * 0.35 +
        diagnosis_validation['validity_score'] * 0.35 +
        treatment_validation['validity_score'] * 0.25 +
        consistency['consistency_score'] * 0.05
    )
    
    return {
        'overall_medical_validity': overall_score,
        'symptom_validity': symptom_validation['validity_score'],
        'diagnosis_validity': diagnosis_validation['validity_score'],
        'treatment_validity': treatment_validation['validity_score'],
        'medical_consistency': consistency['consistency_score'],
        'detailed_validation': {
            'symptoms': symptom_validation,
            'diagnoses': diagnosis_validation,
            'treatments': treatment_validation,
            'consistency': consistency
        }
    }

def assess_dialogue_safety(dialogue_text):
    """ safety assessment of dialogue content"""
    safety_validator = MedicalSafetyValidator()
    return safety_validator.assess_comprehensive_safety(dialogue_text)

def extract_medical_entities_comprehensive(text):
    """Comprehensive medical entity extraction"""
    validator = MedicalConceptValidator()
    return validator.extract_medical_entities(text)