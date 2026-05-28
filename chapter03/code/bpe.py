"""
第三章示例代码2: BPE分词算法
字节对编码的核心实现
"""

import re
import collections


def get_stats(vocab):
    """统计词元对频率"""
    pairs = collections.defaultdict(int)
    for word, freq in vocab.items():
        symbols = word.split()
        for i in range(len(symbols)-1):
            pairs[symbols[i], symbols[i+1]] += freq
    return pairs


def merge_vocab(pair, v_in):
    """合并词元对"""
    v_out = {}
    bigram = re.escape(' '.join(pair))
    p = re.compile(r'(?<!\S)' + bigram + r'(?!\S)')
    for word in v_in:
        w_out = p.sub(''.join(pair), word)
        v_out[w_out] = v_in[word]
    return v_out


# 准备语料库
vocab = {
    'h u g </w>': 1,
    'p u g </w>': 1,
    'p u n </w>': 1,
    'b u n </w>': 1
}

num_merges = 4

print("BPE算法演示")
print("=" * 40)

for i in range(num_merges):
    pairs = get_stats(vocab)
    if not pairs:
        break
    best = max(pairs, key=pairs.get)
    vocab = merge_vocab(best, vocab)
    print(f"第{i+1}次合并: {best} -> {''.join(best)}")
    print(f"新词表: {list(vocab.keys())}")
    print("-" * 40)
