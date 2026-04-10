import os
import re

def universal_stabilize():
    target_dirs = ['.']  # Start from root
    extensions = ['.html', '.py']
    
    # Patterns to catch:
    # 1. {% url 'account_logout' %}
    # 2. {% url 'account_logout' %}
    # 3. reverse('account_logout')
    # 4. reverse('account_logout')
    # 5. reverse_lazy('account_logout')
    
    search_replace = [
        (r"\{% url 'logout' %\}", r"{% url 'account_logout' %}"),
        (r"\{% url \"logout\" %\}", r"{% url 'account_logout' %}"),
        (r"reverse\('logout'\)", r"reverse('account_logout')"),
        (r"reverse\(\"logout\"\)", r"reverse('account_logout')"),
        (r"reverse_lazy\('logout'\)", r"reverse_lazy('account_logout')"),
        (r"reverse_lazy\(\"logout\"\)", r"reverse_lazy('account_logout')"),
    ]
    
    fixed_files = []

    for root, dirs, files in os.walk('.'):
        # Skip .git and external venv if any
        if '.git' in root or 'venv' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    new_content = content
                    for pattern, replacement in search_replace:
                        new_content = re.sub(pattern, replacement, new_content)
                    
                    if content != new_content:
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        fixed_files.append(path)
                        print(f"STABILIZED: {path}")
                except Exception as e:
                    print(f"Error processing {path}: {e}")

    if not fixed_files:
        print("No legacy logout references found.")
    else:
        print(f"Stabilization complete. {len(fixed_files)} files updated.")

if __name__ == "__main__":
    universal_stabilize()
