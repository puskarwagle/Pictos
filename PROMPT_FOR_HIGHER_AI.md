# Architectural Challenge: Managing Visual Assets with Dynamic AI Segmentation

## Context
We are building **NarrateImage**, a tool that takes a video script, segments it using an LLM (like DeepSeek), and suggests/downloads images for each segment based on keywords.

### Current Implementation
1. **Segmentation**: The script is sent to an AI which returns a JSON with `segments` (id, text, keywords).
2. **Storage**: Images are downloaded into a hierarchical folder structure:
   `downloaded_images/{script_name}/{segment_id}/{keyword_slug}/*.jpg`
3. **Linking**: When loading a script, the backend scans the `segment_id` folder and attaches all images found in its subfolders to the segment, regardless of whether the keywords currently match.
4. **UI**: Users can select and delete images. If all images for a keyword are deleted, the keyword folder is removed.

## The Problem
What happens when we re-process a script?
- **Scenario A: New Keywords, Same Segmentation**. The old images are still in the segment folder. They might be irrelevant to the new keywords but useful to the segment.
- **Scenario B: Different Segmentation**. If the AI decides to segment the text differently (e.g., merging segments 1 and 2), the folder `segment/1/` and `segment/2/` might no longer map correctly to the new `segment/1/`.
- **Scenario C: Versioning**. Users might want to keep "good" images even if they change the script slightly.

## Questions for the Higher AI
1. How should we handle the "orphan" image folders when AI response changes?
2. Should we move away from folder-based "segment_id" linking and use a metadata file (e.g., a central SQLite or JSON database) to track which images belong to which *text span* rather than an arbitrary segment index?
3. What is the best strategy to allow "Human-in-the-loop" refinement where a user can lock certain images to specific sentences, even if the AI re-segments the surrounding text?
4. How do we prevent the `downloaded_images` folder from becoming a "junkyard" of unused assets over time?

## Goal
Design a robust linking system that survives script edits and AI re-processing while maintaining the user's manual deletions and selections.
