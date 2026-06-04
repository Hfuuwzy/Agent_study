"""测试环境变量是否正确加载"""
import os
from dotenv import load_dotenv

# 在导入任何其他库之前加载 .env
load_dotenv()

print("环境变量检查:")
print(f"HF_HOME = {os.environ.get('HF_HOME')}")
print(f"SENTENCE_TRANSFORMERS_HOME = {os.environ.get('SENTENCE_TRANSFORMERS_HOME')}")
print(f"TRANSFORMERS_CACHE = {os.environ.get('TRANSFORMERS_CACHE')}")

# 现在导入 sentence_transformers
from sentence_transformers import SentenceTransformer

print("\n模型加载路径测试:")
# 这个模型应该使用缓存
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print(f"模型加载完成")
print(f"模型路径: {model[0].auto_model.config.name_or_path}")
