"""Core PBN integrator functions"""

import time


def matchuj_uczelnie(uczelnia):
    """Match university with PBN"""
    # This would normally call the actual API
    # For now, we'll simulate it

    # Check if we have PBN UID already
    if uczelnia.pbn_uid_id:
        return {"matched": True, "uid": uczelnia.pbn_uid_id}

    # Try to match by name/REGON
    # In real implementation, this would call PBN API
    time.sleep(1)  # Simulate API call

    # For demo, let's just return success
    return {"matched": True, "uid": "demo-uid"}


def importuj_initial(
    uczelnia=None, wydzial_domyslny=None, delete_existing=False, progress_callback=None
):
    """Import initial configuration"""
    if progress_callback:
        progress_callback(0)

    # Simulate some work
    for i in range(0, 101, 20):
        time.sleep(0.5)
        if progress_callback:
            progress_callback(i)

    return {"imported": 5, "failed": 0}


def importuj_zrodla(
    uczelnia=None, wydzial_domyslny=None, delete_existing=False, progress_callback=None
):
    """Import journals"""
    if progress_callback:
        progress_callback(0)

    # Simulate fetching and importing journals
    for i in range(0, 101, 10):
        time.sleep(0.3)
        if progress_callback:
            progress_callback(i)

    return {"imported": 150, "failed": 2}


def importuj_wydawcy(
    uczelnia=None, wydzial_domyslny=None, delete_existing=False, progress_callback=None
):
    """Import publishers"""
    if progress_callback:
        progress_callback(0)

    # Simulate work
    for i in range(0, 101, 25):
        time.sleep(0.2)
        if progress_callback:
            progress_callback(i)

    return {"imported": 45, "failed": 0}


def importuj_konferencje(
    uczelnia=None, wydzial_domyslny=None, delete_existing=False, progress_callback=None
):
    """Import conferences"""
    if progress_callback:
        progress_callback(0)

    # Simulate work
    for i in range(0, 101, 20):
        time.sleep(0.15)
        if progress_callback:
            progress_callback(i)

    return {"imported": 78, "failed": 1}


def importuj_autorzy(
    uczelnia=None, wydzial_domyslny=None, delete_existing=False, progress_callback=None
):
    """Import authors"""
    if progress_callback:
        progress_callback(0)

    # Simulate importing authors - this would be slower
    for i in range(0, 101, 5):
        time.sleep(0.2)
        if progress_callback:
            progress_callback(i)

    return {"imported": 234, "failed": 5}


def importuj_publikacje(
    uczelnia=None, wydzial_domyslny=None, delete_existing=False, progress_callback=None
):
    """Import publications"""
    if progress_callback:
        progress_callback(0)

    # This is usually the longest step
    for i in range(0, 101, 2):
        time.sleep(0.1)
        if progress_callback:
            progress_callback(i)

    return {"imported": 1523, "failed": 12}


def importuj_oswiadczenia(
    uczelnia=None, wydzial_domyslny=None, delete_existing=False, progress_callback=None
):
    """Import statements"""
    if progress_callback:
        progress_callback(0)

    # Simulate work
    for i in range(0, 101, 10):
        time.sleep(0.1)
        if progress_callback:
            progress_callback(i)

    return {"imported": 567, "failed": 3}


def importuj_oplaty(
    uczelnia=None, wydzial_domyslny=None, delete_existing=False, progress_callback=None
):
    """Import fees"""
    if progress_callback:
        progress_callback(0)

    # Simulate work
    for i in range(0, 101, 20):
        time.sleep(0.1)
        if progress_callback:
            progress_callback(i)

    return {"imported": 89, "failed": 0}
