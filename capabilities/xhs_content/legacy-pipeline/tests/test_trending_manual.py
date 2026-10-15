#!/usr/bin/env python3
"""测试热点采集功能。"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trend_detector import get_trending_briefs, get_trending_keywords
from core.config import init

# 初始化
init()

print("=" * 60)
print("热点采集功能测试")
print("=" * 60)

# 测试 1：获取热点关键词（向后兼容）
print("\n【测试 1】获取热点关键词（向后兼容）")
keywords = get_trending_keywords()
print(f"获取到 {len(keywords)} 个热点关键词")
if keywords:
    for kw in keywords[:5]:
        print(f"  - {kw['keyword']} (来源: {kw['source']}, 情感潜力: {kw.get('emotional_potential', '未知')})")

# 测试 2：获取热点 brief
print("\n【测试 2】获取热点 brief（完整信息）")
briefs = get_trending_briefs()
print(f"获取到 {len(briefs)} 个热点 brief")
if briefs:
    for i, brief in enumerate(briefs[:3], 1):
        print(f"\n[{i}] {brief['keyword']}")
        print(f"    来源: {brief['source']}")
        print(f"    情感潜力: {brief['emotional_potential']}")
        print(f"    故事角度提示: {brief['story_angle_hint'][:80]}...")
else:
    print("未获取到热点数据（可能是网络问题或当前没有合适的热点）")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
