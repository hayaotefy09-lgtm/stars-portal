import sys

def check_braces(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    stack = []
    lines = content.split('\n')
    for i, line in enumerate(lines):
        for char in line:
            if char == '{':
                stack.append(i + 1)
            elif char == '}':
                if not stack:
                    print(f"Extra closing brace at line {i + 1}")
                    return
                stack.pop()
    
    if stack:
        print(f"Unclosed braces starting at lines: {stack}")
        for line_num in stack:
            print(f"Line {line_num}: {lines[line_num-1][:100]}")
    else:
        print("Braces are balanced.")

if __name__ == "__main__":
    check_braces(sys.argv[1])
