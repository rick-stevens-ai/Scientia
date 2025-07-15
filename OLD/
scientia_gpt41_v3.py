        # 1) Generate or Evolve Ideas
            try:
                for i, idea in enumerate(ideas):
                    # Extract idea-specific feedback for this idea from the overall reflection
                    idea_specific_feedback = extract_idea_specific_feedback(reflection_output, i+1, len(ideas))
                    reflection_entry = f"{idea}\n\n--- REFLECTION FEEDBACK ---\n\n{idea_specific_feedback}"
                    log_idea(scientia_dir, i+1, reflection_entry, "Reflection", round_idx+1)
            except Exception as e:
                print(f"Warning: Failed to log reflection: {e}")
                traceback.print_exc()
            try:
                for i, idea in enumerate(ideas):
                    # Extract idea-specific feedback for proximity check
                    idea_specific_proximity = extract_idea_specific_feedback(proximity_output, i+1, len(ideas))
                    proximity_entry = f"{idea}\n\n--- PROXIMITY CHECK FEEDBACK ---\n\n{idea_specific_proximity}"
                    log_idea(scientia_dir, i+1, proximity_entry, "Proximity Check", round_idx+1)
            except Exception as e:
        }

        # Extract key information from first and last version of the idea
        initial_idea_entry = evolution_history[0] if evolution_history else None
        final_idea_entry = evolution_history[-1] if evolution_history else None
        initial_idea_text = initial_idea_entry["content"] if initial_idea_entry else ""
        
        # Extract structured sections from initial and final ideas
        initial_sections = parse_structured_idea(initial_idea_text)
        final_sections = parse_structured_idea(idea_text)
        
        # Generate the report content
        report_content = f"""# Final Report: Idea {idea_num}

## Fi        # Add detailed change analysis and track the idea's evolution
        if i > 0:
            prev_entry = evolution_history[i-1]
            prev_sections = parse_structured_idea(prev_entry['content'])
            current_sections = parse_structured_idea(entry['content'])
            
            # Check for significant changes in key components
            changes = []
            
            # Compare title
            if prev_sections.get("title") != current_sections.get("title"):
                if prev_sections.get("title") and current_sections.get("title"):
                    changes.append(f"**Title changed:** from \"{prev_sections['title']}\" to \"{current_sections['title']}\"")
            
            # Compare key idea
            if prev_sections.get("key_idea") != current_sections.get("key_idea"):
                changes.append("**Key idea refined**")
                
            # Compare approach
            if prev_sections.get("approach") != current_sections.get("approach"):
                changes.append("**Methodology updated**")
                
            # Check for new citations
            prev_citations = extract_citations(prev_entry['content'])
            current_citations = extract_citations(entry['content'])
            new_citations = [c for c in current_citations if c not in prev_citations]
            
            if new_citations:
                changes.append(f"**New citations added:** {', '.join(new_citations)}")
                
            # Add the changes to the report
            if changes:
                report_content += "**Key changes:**\n"
                for change in changes:
                    report_content += f"- {change}\n"
                report_content += "\n"
        
        # Add citations section
        if citations:
            report_content += "## Citations\n\n"
            for citation in citations:
                report_content += f"- {citation}\n"
                
        # Add section comparing initial and final versions
        if initial_idea_entry and initial_idea_entry != final_idea_entry:
            initial_sections = parse_structured_idea(initial_idea_entry["content"])
            report_content += "\n## Comparison of Initial vs. Final Version\n\n"
            
            report_content += "### Initial Version\n\n"
            if initial_sections.get("title"):
                report_content += f"**Title:** {initial_sections['title']}\n\n"
            if initial_sections.get("key_idea"):
                report_content += f"**Key Idea:** {initial_sections['key_idea']}\n\n"
                
            report_content += "### Final Version\n\n"
            if final_sections.get("title"):
                report_content += f"**Title:** {final_sections['title']}\n\n"
            if final_sections.get("key_idea"):
                report_content += f"**Key Idea:** {final_sections['key_idea']}\n\n"
                
            # Add analysis of key improvements
            initial_citations = extract_citations(initial_idea_entry["content"])
            final_citations = extract_citations(idea_text)
            new_citations = [c for c in final_citations if c not in initial_citations]
            
            report_content += "### Key Improvements\n\n"
            if new_citations:
                report_content += f"- **Added {len(new_citations)} new citations** to strengthen the theoretical foundation\n"
            
            # Compare length and detail
            initial_length = len(initial_idea_entry["content"])
            final_length = len(idea_text)
            if final_length > initial_length * 1.2:  # At least 20% longer
                report_content += f"- **Expanded detail:** Final version is {int((final_length/initial_length - 1) * 100)}% more detailed\n"
            
            # Compare approach sections
            if initial_sections.get("approach") != final_sections.get("approach") and final_sections.get("approach"):
                report_content += "- **Refined methodology:** The approach was updated to be more specific and actionable\n"
process.

## Evolution Highlights

The idea underwent several iterations during the research process:
        log_file_path: Path to the idea's log file
        
    Returns:
        True if report was generated successfully, False otherwise
    """
    try:
        report_file = os.path.join(scientia_dir, f"idea_{idea_num}_final.md")
        
        # Extract citations from the idea text
        citations = extract_citations(idea_text)
        
        # Read the evolution history from the log file
        evolution_history = []
        evolution_phases = {}  # Dictionary to track the latest entry for each phase
        
        with open(log_file_path, 'r', encoding='utf-8') as f:
            log_content = f.read()
            
            # Split log into entries by the separator
            entries = log_content.split("="*80)
            
            # Process each entry
            for entry in entries:
                if entry.strip():
                    # Parse timestamps, phases, and content
                    timestamp_match = re.search(r'TIMESTAMP: (.*?)$', entry, re.MULTILINE)
                    phase_match = re.search(r'PHASE: (.*?)(?:, ROUND:|, ELO SCORE:|$)', entry, re.MULTILINE)
                    round_match = re.search(r'ROUND: (\d+)', entry)
                    elo_match = re.search(r'ELO SCORE: (\d+\.\d+)', entry)
                    
                    # Skip header entry (first entry might be just the header)
                    if timestamp_match and phase_match:
                        timestamp = timestamp_match.group(1).strip()
                        phase = phase_match.group(1).strip()
                        round_num = int(round_match.group(1)) if round_match else None
                        elo_score = float(elo_match.group(1)) if elo_match else None
                        
                        # Extract content after the metadata section
                        content_parts = entry.split("\n\n", 1)
                        content = content_parts[1] if len(content_parts) > 1 else ""
                        
                        entry_data = {
                            "timestamp": timestamp,
        ]
        
        for pattern in idea_patterns:
            matches = re.finditer(pattern, feedback_text, re.DOTALL)
            for match in matches:
                extracted_text = match.group(0).strip()
                if len(extracted_text) > 50:  # Longer minimum to ensure meaningful content
               try:
                                matchup_log_b += f"\nVector-based score: {1-vector_score:.3f}\n"
                        matchup_log_b
ceback.print_exc()
e}")
                traceback.print_exc()
ction: {e}")
                traceback.print_exc()
e and len(idea_title.split()) >= 3:
                # Take the first 5-7 words as a distinctive title phrase
                title_words = idea_title.split()[:min(7, len(idea_title.split()))]
                key_phrases.append(' '.join(title_words))
            
            # Add key concept phrases if available
            if idea_key_concepts:
                # Split into sentences and take the first sentence
                first_sentence = idea_key_concepts.split('.')[0]
                if len(first_sentence.split()) >= 5:  # Only if reasonably distinctive
                    key_phrases.append(first_sentence)
            
            # Look for sections containing these key phrases
            for phrase in key_phrases:
                if len(phrase) > 15:  # Only use phrases that are distinctive enough
                    # Escape special regex characters
                    safe_phrase = re.escape(phrase[:40])  # Limit length for regex performance
                    phrase_pattern = fr'(?i)(?:^|\n)(?:.*?{safe_phrase}.*?)(?:\n|$).*?(?=\n(?:##|\d+\.|\*\*)|\Z)'
                    matches = re.finditer(phrase_pattern, feedback_text, re.DOTALL)
                    for match in matches:
                        extracted_text = match.group(0).strip()
                        if len(extracted_text) > 100:  # Must be substantial
                            return extracted_text
        
                try:
                    for i, idea in enumerate(ideas):
                        # Extract idea-specif        # We already extracted these above, no need to repeat
                try:
                    # Compare with previous entry to identify changes
                    prev_entry = evolution_history[i-1]
                    prev_content = prev_entry['content']
                    curr_content = entry['content']
                    
                    # Parse structured sections
                    prev_sections = parse_structured_idea(prev_content)
                    curr_sections = parse_structured_idea(curr_content)
                    
                    # Check for significant changes
                    changes = []
                    
                    # Compare titles
                    if prev_sections.get("title") != curr_sections.get("title"):
                        if prev_sections.get("title") and curr_sections.get("title"):
                            changes.append(f"**Title refined:** from \"{prev_sections['title']}\" to \"{curr_sections['title']}\"")
                    
                    # Compare key ideas
                    if prev_sections.get("key_idea") != curr_sections.get("key_idea"):
                        changes.append("**Key idea enhanced or clarified**")
                    
                    # Check for new citations
                    prev_citations = extract_citations(prev_content)
                    curr_citations = extract_citations(curr_content)
                    new_citations = [c for c in curr_citations if c not in prev_citations]
                    
                    if new_citations:
                        changes.append(f"**Citations added:** {', '.join(new_citations)}")
                    
                    # Add changes to report
                    if changes:
                        report_content += "**Key changes from previous version:**\n"
                        for change in changes:
                            report_content += f"- {change}\n"
                        report_content += "\n"
                        
                except Exception as e:
                    # If comparison fails, continue without detailed change analysis
                    print(f"Warning: Failed to analyze changes: {e}")

                except Exception as e:
                    print(f"Warning: Failed to log ranking: {e}")
                    traceback.print_exc()
     except Exception as e:
                print(f"Warning: Failed to log proximity check: {e}")
                traceback.print_exc()
dx+1)
            except Exception as e:
                print(f"Warning: Failed to log reflection: {e}")
                traceback.print_exc()
    # Create meta-review prompt
    meta_prompt = (
        f"Here are the final top 5 ideas based on tournament results:\n\n"
        f"{final_ideas_text}\n\n"
        "Please provide a comprehensive meta-review that addresses the following:\n\n"
        "1. Summarize each of the top 5 ideas, highlighting their core hypotheses and key innovations\n"
        "2. Analyze the strengths and limitations of each idea, noting potential impact and feasibility\n"
        "3. Identify cross-cutting themes or complementary approaches across these ideas\n"
        "4. Suggest practical next steps for validating or implementing each idea\n"
        "5. Recommend potential collaborations or interdisciplinary connections\n\n"
        "For each idea, include relevant citations from the existing references, and suggest "
        "additional key literature in the format [Author Year] that would strengthen the research. "
        "Your meta-review should synthesize the final, evolved state of each idea, including "
        "improvements made throughout the iterative process."
    )
    
    # Call the meta-review agent
    meta_review_output = call_agent(
        # Extract just the title and key                try:
                    # Compare with previous entry to identify changes
                    prev_entry = evolution_history[i-1]
                    prev_content = prev_entry['content']
                    curr_content = entry['content']
                    
                    # Parse structured sections
                    prev_sections = parse_structured_idea(prev_content)
                    curr_sections = parse_structured_idea(curr_content)
                    
                    # Check for significant changes
                    changes = []
                    
                    # Compare titles
                    if prev_sections.get("title") != curr_sections.get("title"):
                        if prev_sections.get("title") and curr_sections.get("title"):
                            changes.append(f"**Title refined:** from \"{prev_sections['title']}\" to \"{curr_sections['title']}\"")
                    
                    # Compare key ideas
                    if prev_sections.get("key_idea") != curr_sections.get("key_idea"):
                        changes.append("**Key idea enhanced or clarified**")
                    
                    # Check for new citations
                    prev_citations = extract_citations(prev_content)
                    curr_citations = extract_citations(curr_content)
                    new_citations = [c for c in curr_citations if c not in prev_citations]
                    
                    if new_citations:
                        changes.append(f"**Citations added:** {', '.join(new_citations)}")
                    
                    # Add changes to report
                    if changes:
                        report_content += "**Key changes from previous version:**\n"
                        for change in changes:
                            report_content += f"- {change}\n"
                        report_content += "\n"
                        
                except Exception as e:
                    # If comparison fails, continue without detailed change analysis
                    print(f"Warning: Failed to analyze changes: {e}")
arse_structured_idea(idea)
        # Extract hypotheses if needed
        if len(ideas) == 1 and '**Hypothesis:**' in ideas[0]:
            ideas = parse_ideas_from_tournament_text(ideas[0])
            if len(ideas) < 2:
                print("ERROR: Could not extract multiple hypotheses from the text.")
                return [(ideas[0], 1500.0)]
        
        # Filter out incomplete or invalid ideas with better logging
        valid_ideas = []
        invalid_ideas = []
        for i, idea in enumerate(ideas):
            if is_valid_idea(idea):
                valid_ideas.append(idea)
            else:
                invalid_ideas.append((i+1, idea))
                print(f"WARNING: Idea {i+1} is incomplete or invalid and will be excluded from the tournament.")
                print(f"Preview: {idea[:100]}...")
                
                # Log detailed validation failure reasons for debugging
                if not idea or len(idea            print(f"WARNING: Idea {i+1} is incomplete or invalid and will be excluded from the tournament.")
            print(f"Preview: {idea[:100]}...")
            
            # Print detailed diagnostics about the failed validation
            sections = parse_structured_idea(idea)
            section_info = ", ".join([f"{k}: {len(v)}" for k, v in sections.items() if v])
            print(f"  Content sections found: {section_info or 'none'}")
            print(f"  Total length: {len(idea.strip())}")
        
        if len(valid_ideas) < 2:
            print("ERROR: Not enough valid ideas for tournament. Need at least 2.")
            
            # Try a more lenient approach to salvage ideas
            print("Attempting to use basic text content from ideas...")
            salvaged_ideas = []
            
            for idea in ideas:
                if len(idea.strip()) >= 50:  # Very minimal length requirement
                    salvaged_ideas.append(idea)
                    
            if len(salvaged_ideas) >= 2:
                print(f"Salvaged {len(salvaged_ideas)} ideas. Proceeding with tournament.")
                valid_ideas = salvaged_ideas
            else:
                # Return all ideas with default ratings
                print("Failed to salvage enough ideas. Using default ratings.")
                return [(idea, 1500.0) for idea in ideas]
n(valid_ideas) < 2:
            print("WARNING: Not enough valid ideas for traditional tournament. Need at least 2.")
            
            # Fallback: If we have invalid ideas, try to repair them
            if invalid_ideas and len(ideas) >= 2:
                print("Attempting to repair invalid ideas for tournament...")
                
                # For each invalid idea, try to extract useful content and reformat
                repaired_ideas = []
                for idx, invalid_idea in invalid_ideas:
                    # Extract any usable content
                    sections = parse_structured_idea(invalid_idea)
                    
                    # If we have any content, create a simplified version
                    content_parts = []
                    if sections.get("title"):
                        content_parts.append(f"**Title**: {sections['title']}")
                    
                    if sections.get("key_idea"):
                        content_parts.append(f"**Key Idea**: {sections['key_idea']}")
                    elif len(invalid_idea) > 50:
                        # Extract first paragraph as key idea
                        first_para = invalid_idea.split('\n\n')[0].strip()
                        if len(first_para) > 30:
                            content_parts.append(f"**Key Idea**: {first_para[:300]}")
                    
                    if content_parts:
                        repaired_idea = "\n\n".join(content_parts)
                        print(f"Repaired idea {idx}: {repaired_idea[:100]}...")
                        repaired_ideas.append(repaired_idea)
                
                # If we have enough repaired ideas, use them
                if len(valid_ideas) + len(repaired_ideas) >= 2:
                    valid_ideas.extend(repaired_ideas)
                    print(f"Successfully repaired {len(repaired_ideas)} ideas. Proceeding with tournament.")
                else:
                    # Still not enough ideas, use original ideas with default ratings
                    print("Repair unsuccessful. Using original ideas with default ratings.")
                    return [(idea, 1500.0) for idea in ideas]
            else:
                # Not enough ideas, return with default ratings
                print("Using all available ideas with default ratings.")
                return [(idea, 1500.0) for idea in ideas]
    # Run the tournament with better error handling
    try:
        tournament_results = run_tournament(ideas, get_tournament_agent_prompt(), scientia_dir)
        
        # If tournament failed to return results (e.g., not enough valid ideas),
        # create default ratings for all ideas
        if not tournament_results:
            print("WARNING: Tournament returned no results. Using default ELO ratings.")
            tournament_results = [(idea, 1500.0) for idea in ideas]
    except Exception as e:
        print(f"ERROR: Tournament execution failed: {e}")
        traceback.print_exc()
        # Fallback to default ratings
        tournament_results = [(idea, 1500.0) for idea in ideas]
    
    # Log final tournament results for each idea
    if scientia_dir:
        try:
            print("\nLogging final tournament results...")
            for i, (idea, rating) in enumerate(tournament_results):
                # Find the idea's index in the original list
                original_idx = ideas.index(idea) if idea in ideas else i
                tournament_entry = f"Final ELO Rating: {rating:.1f}\n\nRank: {i+1} out of {len(tournament_results)}\n\n{idea}"
                log_idea(scientia_dir, original_idx+1, tournament_entry, "Final Tournament Results", elo_score=rating)
        except Exception as e:
            print(f"Warning: Failed to log final tournament results: {e}")
            traceback.print_exc()
