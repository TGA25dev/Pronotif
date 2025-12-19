import hashlib

def generate_id(arg:str) -> str:
    """Creates a unique id based on the given string"""
    
    if not arg:
        return ""
        
    return hashlib.md5(str(arg).strip().encode('utf-8')).hexdigest() #Create the hash