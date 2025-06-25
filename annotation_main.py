import json
import logging
import os
from Agents.AnnotatorAgent import RemediNLUAnnotatorAgent
from Models.labels import RemediAnnotatedTurn, DialogueAnnotationOutput
from Utils.llms_utils import load_gpt_model 
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_dialogue_file(input_filepath: str, output_filepath: str):
    logger.info(f"Starting enhanced ReMeDi-style annotation for: {input_filepath}")

    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            original_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_filepath}")
        return
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from input file: {input_filepath}")
        return

    # ENHANCED: Initialize annotator with better configuration
    annotator_agent = RemediNLUAnnotatorAgent()

    dialogue_turns = original_data.get("dialogue") 
    
    if not isinstance(dialogue_turns, list):
        logger.error(f"Input JSON {input_filepath} does not contain a 'dialogue' list or it's not a list.")
        # Create empty annotation file
        empty_output_data = DialogueAnnotationOutput(
            source_row_id=original_data.get("partial_profile", {}).get("row_id"),
            source_subject_id=original_data.get("partial_profile", {}).get("subject_id"),
            source_hadm_id=original_data.get("partial_profile", {}).get("hadm_id")
        )
        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
        with open(output_filepath, 'w', encoding='utf-8') as f_out:
            json.dump(empty_output_data.model_dump(), f_out, indent=2)
        logger.info(f"Saved empty annotation structure to {output_filepath} due to missing/malformed dialogue in input.")
        return

    remedi_annotated_turns_list = []
    successful_annotations = 0
    total_labels_extracted = 0

    # ENHANCED: Process with better logging and validation
    for turn_id, turn_data in enumerate(dialogue_turns):
        role = turn_data.get("role")
        utterance_text = turn_data.get("content")

        if not role or not utterance_text:
            logger.warning(f"Skipping turn {turn_id} due to missing role or content.")
            annotated_turn = RemediAnnotatedTurn(
                turn_id=turn_id,
                role=role or "Unknown",
                utterance_text=utterance_text or "",
                remedi_labels=[]
            )
            remedi_annotated_turns_list.append(annotated_turn)
            continue
        
        # ENHANCED: Better utterance preprocessing
        clean_utterance = utterance_text.strip()
        if len(clean_utterance) < 3:  # Skip very short utterances
            logger.warning(f"Skipping very short utterance at turn {turn_id}: '{clean_utterance}'")
            annotated_turn = RemediAnnotatedTurn(
                turn_id=turn_id,
                role=role,
                utterance_text=utterance_text,
                remedi_labels=[]
            )
            remedi_annotated_turns_list.append(annotated_turn)
            continue
        
        logger.info(f"Annotating Turn {turn_id}: {role} - \"{clean_utterance[:80]}{'...' if len(clean_utterance) > 80 else ''}\"")
        
        try:
            # ENHANCED: Annotation with timing
            start_time = time.time()
            labels = annotator_agent.annotate_utterance(clean_utterance, role)
            annotation_time = time.time() - start_time
            
            # ENHANCED: Quality validation
            if labels:
                successful_annotations += 1
                total_labels_extracted += len(labels)
                
                # Log label details for monitoring
                label_summary = []
                for label in labels:
                    label_summary.append(f"{label.slot}:{label.value[:20]}")
                
                logger.info(f"  ✅ Extracted {len(labels)} labels in {annotation_time:.2f}s: {', '.join(label_summary)}")
            else:
                logger.warning(f"  ⚠️ No labels extracted for turn {turn_id}")
            
            annotated_turn = RemediAnnotatedTurn(
                turn_id=turn_id,
                role=role,
                utterance_text=utterance_text,
                remedi_labels=labels
            )
            remedi_annotated_turns_list.append(annotated_turn)
            
            # ENHANCED: Rate limiting to avoid API throttling
            time.sleep(0.1)  # Small delay between annotations
            
        except Exception as e:
            logger.error(f"Error annotating utterance for turn_id {turn_id}: {e}", exc_info=True)
            annotated_turn = RemediAnnotatedTurn(
                turn_id=turn_id,
                role=role,
                utterance_text=utterance_text,
                remedi_labels=[]
            )
            remedi_annotated_turns_list.append(annotated_turn)

    # ENHANCED: Create output with quality metrics
    output_data = DialogueAnnotationOutput(
        source_row_id=original_data.get("partial_profile", {}).get("row_id"),
        source_subject_id=original_data.get("partial_profile", {}).get("subject_id"),
        source_hadm_id=original_data.get("partial_profile", {}).get("hadm_id"),
        remedi_style_dialogue_annotations=remedi_annotated_turns_list
    )
    
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f_out:
            json.dump(output_data.model_dump(), f_out, indent=2)
        
        # ENHANCED: Detailed success logging
        success_rate = (successful_annotations / len(dialogue_turns)) * 100 if dialogue_turns else 0
        avg_labels_per_turn = total_labels_extracted / successful_annotations if successful_annotations > 0 else 0
        
        logger.info(f"✅ Successfully annotated and saved to: {output_filepath}")
        logger.info(f"📊 Quality Metrics:")
        logger.info(f"   - Total turns: {len(dialogue_turns)}")
        logger.info(f"   - Successfully annotated: {successful_annotations}")
        logger.info(f"   - Success rate: {success_rate:.1f}%")
        logger.info(f"   - Total labels extracted: {total_labels_extracted}")
        logger.info(f"   - Average labels per successful turn: {avg_labels_per_turn:.1f}")
        
    except Exception as e:
        logger.error(f"Error saving output JSON file: {output_filepath}. Error: {e}")

def validate_input_directory(input_dir: str) -> bool:
    """ENHANCED: Validate input directory and provide helpful feedback"""
    if not os.path.exists(input_dir):
        logger.error(f"❌ Input directory '{input_dir}' does not exist.")
        logger.info(f"💡 Please ensure the directory exists and contains dialogue JSON files.")
        return False
    
    json_files = [f for f in os.listdir(input_dir) if f.startswith("dialogue_output_") and f.endswith(".json")]
    
    if not json_files:
        logger.warning(f"⚠️ No 'dialogue_output_*.json' files found in '{input_dir}'")
        logger.info(f"💡 Expected files should follow pattern: dialogue_output_*.json")
        all_json = [f for f in os.listdir(input_dir) if f.endswith(".json")]
        if all_json:
            logger.info(f"📁 Found these JSON files instead: {all_json[:5]}")
        return False
    
    logger.info(f"✅ Found {len(json_files)} dialogue files to process")
    return True

def process_with_enhanced_monitoring(input_json_dir: str, output_annotated_dir: str):
    """ENHANCED: Process with comprehensive monitoring and reporting"""
    
    if not validate_input_directory(input_json_dir):
        return
    
    # Get all files to process
    json_files = [f for f in os.listdir(input_json_dir) if f.startswith("dialogue_output_") and f.endswith(".json")]
    
    logger.info(f"🚀 Starting enhanced annotation processing for {len(json_files)} files")
    logger.info(f"📂 Input directory: {input_json_dir}")
    logger.info(f"📂 Output directory: {output_annotated_dir}")
    
    # Processing statistics
    processed_files_count = 0
    failed_files_count = 0
    total_start_time = time.time()
    
    for i, filename in enumerate(json_files, 1):
        file_start_time = time.time()
        
        input_filepath = os.path.join(input_json_dir, filename)
        output_filename = filename.replace("dialogue_output_", "remedi_annotated_")
        output_filepath = os.path.join(output_annotated_dir, output_filename)
        
        logger.info(f"\n📄 Processing file {i}/{len(json_files)}: {filename}")
        
        try:
            process_dialogue_file(input_filepath, output_filepath)
            processed_files_count += 1
            
            file_time = time.time() - file_start_time
            logger.info(f"✅ Completed {filename} in {file_time:.1f}s")
            
        except Exception as e:
            failed_files_count += 1
            logger.error(f"❌ Failed to process {filename}: {e}")
            continue
    
    # ENHANCED: Final summary report
    total_time = time.time() - total_start_time
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🎯 ENHANCED ANNOTATION PROCESSING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"📊 Processing Summary:")
    logger.info(f"   ✅ Successfully processed: {processed_files_count}")
    logger.info(f"   ❌ Failed: {failed_files_count}")
    logger.info(f"   🎯 Success rate: {(processed_files_count/(processed_files_count+failed_files_count))*100:.1f}%")
    logger.info(f"   ⏱️ Total time: {total_time:.1f}s")
    logger.info(f"   ⚡ Average time per file: {total_time/len(json_files):.1f}s")
    logger.info(f"📂 Enhanced annotations saved to: {output_annotated_dir}")
    
    if processed_files_count > 0:
        logger.info(f"\n🔍 Next steps:")
        logger.info(f"   1. Run annotation validation to check quality")
        logger.info(f"   2. Review annotation results in {output_annotated_dir}")
        logger.info(f"   3. Use evaluation metrics to assess performance")


if __name__ == "__main__":
    # ENHANCED: Configuration
    input_json_dir = "output_dialogue"  # Updated to use SOTA output
    output_annotated_dir = "output_annotated"
    
    # ENHANCED: Process with monitoring
    process_with_enhanced_monitoring(input_json_dir, output_annotated_dir)