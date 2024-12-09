def test_home_route(client):
    """
    Test the home route
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json == {"message": "Server is up and running"}

def test_get_trips_without_params(client):
    """
    Test the /trips route without query parameters
    """
    response = client.get("/trips")
    assert response.status_code == 200
    assert isinstance(response.json, list)  # Should return a list

def test_get_trips_with_params(client):
    """
    Test the /trips route with query parameters
    """
    response = client.get("/trips", query_string={
        "pickup_long": -73.93981170654298,
        "pickup_lat": 40.81560134887695
    })
    assert response.status_code == 200
    assert isinstance(response.json, list)  # Should return a list

def test_get_trip_stats(client):
    """
    Test the /trips/stats route
    """
    response = client.get("/trips/stats")
    assert response.status_code == 200
    assert "average_trip_duration" in response.json
    assert "total_days" in response.json
    assert "trips_per_day" in response.json
