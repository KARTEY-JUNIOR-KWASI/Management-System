import os
import re

def fix_templates(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if '{% static' in content and '{% load static' not in content:
                        print(f"Fixing {file_path}...")
                        
                        # Find extends tag
                        extends_match = re.search(r'({% extends [^%]+ %})', content)
                        
                        if extends_match:
                            # Insert after extends
                            insert_pos = extends_match.end()
                            new_content = content[:insert_pos] + "\n{% load static %}" + content[insert_pos:]
                        else:
                            # Insert at top
                            new_content = "{% load static %}\n" + content
                            
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

if __name__ == "__main__":
    fix_templates('templates')
