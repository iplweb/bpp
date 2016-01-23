def test():
    from fabtools import require, deb
    deb.update_index()
    require.postgres.server()
