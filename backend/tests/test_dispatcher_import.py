def test_dispatcher_imports():
    from backend.app.services.dispatcher import BookingDispatcher

    assert BookingDispatcher is not None