# Third-party model notice

SoilLens optionally downloads and runs the following model locally:

- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Purpose: multilingual semantic text retrieval
- Upstream: https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- Runtime distribution used by FastEmbed: `qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`
- License: Apache License 2.0

Model files are downloaded to `.cache/fastembed/` at runtime and are not part of
the project source or public data package.
