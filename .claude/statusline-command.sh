#!/bin/bash
# Claude Code status line script
# Displays: model | tokens | ctx progress | cost | 5h quota | project | git

input=$(cat)

python3 -c "
import json, sys, os, subprocess

data = json.loads(sys.stdin.read())
parts = []

# ── Model ──
model = data.get('model', {}).get('display_name', '')
if model:
    parts.append(model)

# ── Token I/O ──
ctx = data.get('context_window', {})
in_tok = ctx.get('total_input_tokens', 0)
out_tok = ctx.get('total_output_tokens', 0)
def fmt(n):
    if n >= 1000000:
        return f'{n/1000000:.1f}M'
    if n >= 1000:
        return f'{n/1000:.1f}k'
    return str(n)
if in_tok or out_tok:
    parts.append(f'In:{fmt(in_tok)} Out:{fmt(out_tok)}')

# ── API calls (count from transcript JSONL) ──
transcript = data.get('transcript_path', '')
api_calls = 0
if transcript and os.path.isfile(transcript):
    try:
        with open(transcript, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get('type') == 'assistant':
                        api_calls += 1
                except:
                    pass
    except:
        pass
if api_calls > 0:
    parts.append(f'API:{api_calls}')

# ── Context usage + progress bar ──
used_pct = ctx.get('used_percentage', 0)
remaining_pct = ctx.get('remaining_percentage', 0)
used_tok = ctx.get('total_input_tokens', 0) + ctx.get('total_output_tokens', 0)
window = ctx.get('context_window_size', 0)

if used_pct:
    bar_len = 12
    filled = round(used_pct / 100 * bar_len)
    empty = bar_len - filled
    bar = '#' * filled + '-' * empty
    parts.append(f'Ctx:{bar} {used_pct:.0f}% ({fmt(used_tok)}/{fmt(window)})')

# ── 5-hour rate limit ──
rl = data.get('rate_limits', {})
five_hour = rl.get('five_hour', {}).get('used_percentage')
if five_hour is not None:
    bar_len = 8
    filled = round(five_hour / 100 * bar_len)
    empty = bar_len - filled
    bar = '#' * filled + '-' * empty
    parts.append(f'5h:{bar} {five_hour:.0f}%')

# ── Cost ──
cost = data.get('cost', {})
total_cost = cost.get('total_cost_usd', 0)
duration_ms = cost.get('total_duration_ms', 0)
cost_str = f'\${total_cost:.2f}' if total_cost else ''
if duration_ms:
    secs = duration_ms / 1000
    if secs >= 60:
        mins = int(secs // 60)
        secs_left = int(secs % 60)
        cost_str += f' {mins}m{secs_left}s'
    else:
        cost_str += f' {secs:.0f}s'
if cost_str:
    parts.append(cost_str.strip())

# ── Project path + Git branch ──
project = data.get('workspace', {}).get('project_dir', '')
git_branch = ''
if project and os.path.isdir(project):
    try:
        git_branch = subprocess.check_output(
            ['git', 'branch', '--show-current'],
            cwd=project, stderr=subprocess.DEVNULL
        ).decode('utf-8', errors='ignore').strip()
    except:
        pass
if project:
    proj_name = os.path.basename(project.replace('\\\\', '/'))
    if git_branch:
        parts.append(f'{proj_name} ({git_branch})')
    else:
        parts.append(proj_name)

# ── Flags ──
flags = []
if data.get('fast_mode'):
    flags.append('Fast')
if data.get('thinking', {}).get('enabled'):
    flags.append('Think')
effort = data.get('effort', {}).get('level', '')
if effort and effort != 'high':
    flags.append(f'Eff:{effort}')
if flags:
    parts.append(' '.join(flags))

print(' | '.join(parts))
" <<< "$input"
