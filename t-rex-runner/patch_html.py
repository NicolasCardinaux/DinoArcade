import sys

with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
skip = False
for line in lines:
    if '<template id="audio-resources">' in line:
        out.append('            <template id="audio-resources">\n')
        out.append('                <audio id="offline-sound-press" src="assets/jump.wav"></audio>\n')
        out.append('                <audio id="offline-sound-hit" src="assets/hit.wav"></audio>\n')
        out.append('                <audio id="offline-sound-reached" src="assets/score.wav"></audio>\n')
        out.append('            </template>\n')
        skip = True
        continue
    if skip and '</template>' in line:
        skip = False
        continue
    if not skip:
        out.append(line)

with open('index.html', 'w', encoding='utf-8') as f:
    f.writelines(out)
