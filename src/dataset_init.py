import hashlib

def _cache_key(*parts):
	raw = "||".join(str(p) for p in parts)
	return hashlib.md5(raw.encode()).hexdigest()
