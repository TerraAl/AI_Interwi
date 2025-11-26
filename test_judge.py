#!/usr/bin/env python3
"""Test judge evaluation locally"""
import asyncio
import sys
sys.path.insert(0, 'hirecode-ai-openai/backend')

from judge import SubmissionJudge
from runner import SupportedLanguage

async def test_judge():
    judge = SubmissionJudge()
    
    # Simple Python code that should pass two_sum tests
    code = """
n = int(input())
nums = list(map(int, input().split()))
target = int(input())

for i in range(n):
    for j in range(i + 1, n):
        if nums[i] + nums[j] == target:
            print(i, j)
            exit()
"""
    
    try:
        print("[TEST] Starting judge evaluation for two_sum")
        result = await judge.evaluate(code, SupportedLanguage.PYTHON, "two_sum")
        
        print(f"\n[TEST] Judge result keys: {list(result.keys())}")
        print(f"[TEST] Task ID: {result['task_id']}")
        print(f"[TEST] Overall passed: {result['passed']}")
        print(f"[TEST] Visible tests count: {len(result['visible_tests'])}")
        print(f"[TEST] Hidden tests passed: {result['hidden_tests_passed']}")
        
        if result['visible_tests']:
            print(f"\n[TEST] First visible test:")
            test = result['visible_tests'][0]
            print(f"  Input: {repr(test['input'])}")
            print(f"  Expected: {repr(test['expected'])}")
            print(f"  Got: {repr(test['stdout'])}")
            print(f"  Passed: {test['passed']}")
            print(f"  Elapsed: {test['elapsed_ms']}ms")
            
        print(f"\n[TEST] Metrics: {result['metrics']}")
        
    except Exception as e:
        print(f"[TEST] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_judge())
