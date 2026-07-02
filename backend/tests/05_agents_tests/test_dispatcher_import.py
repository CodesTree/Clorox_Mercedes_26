def test_dispatcher_imports():
    from app.services.dispatcher import BookingDispatcher

    assert BookingDispatcher is not None