def rename_dict_key(data, old_key, new_key):
    """
    Recursively rename a dictionary key in a dictionary and all nested dictionaries.

    Args:
        data: Dictionary or any data structure that may contain dictionaries
        old_key: The key to be renamed
        new_key: The new key name

    Returns:
        The modified data structure with renamed keys
    """
    if isinstance(data, dict):
        # Create a new dictionary with renamed keys
        new_dict = {}
        for key, value in data.items():
            # Rename the key if it matches
            new_key_name = new_key if key == old_key else key
            # Recursively process the value
            new_dict[new_key_name] = rename_dict_key(value, old_key, new_key)
        return new_dict
    elif isinstance(data, list):
        # Process each item in the list
        return [rename_dict_key(item, old_key, new_key) for item in data]
    else:
        # Return the value unchanged if it's not a dict or list
        return data
