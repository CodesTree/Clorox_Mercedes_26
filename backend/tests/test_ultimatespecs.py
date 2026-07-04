"""UltimateSpecs parser/ingest tests (fixtures only, no network)."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import orm
from app.orm import TrainingData, VehicleSpec
from scraper.ultimatespecs import UltimateSpecsExtractor, _is_approved_generation_url, run

FIXTURES = Path(__file__).resolve().parents[1] / "scraper" / "fixtures"


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'ultimatespecs.db').as_posix()}")
    orm.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def test_ultimatespecs_fixture_parses_c200_engineering_fields():
    html = (FIXTURES / "ultimatespecs_c200_detail.html").read_text(encoding="utf-8")
    row = UltimateSpecsExtractor().extract_detail(
        html,
        source_url="https://www.ultimatespecs.com/fixture/mercedes-c200",
    )

    assert row is not None
    assert row["source"] == "ultimatespecs"
    assert row["make"] == "Mercedes-Benz"
    assert row["model"] == "C_CLASS"
    assert row["variant"] == "C200"
    assert row["generation"] == "W206"
    assert row["year_start"] == 2021
    assert row["year_end"] == 2024
    assert row["engine_type"] == "Inline 4"
    assert row["engine_cc"] == 1496
    assert row["engine_aspiration"] == "Turbo + electric compressor"
    assert row["transmission"] == "9 speed Automatic"
    assert row["number_of_gears"] == 9
    assert row["top_speed_kmh"] == 246
    assert row["boot_space_litres"] == 455
    assert row["seat_capacity"] == 5
    assert row["number_of_doors"] == 4
    assert row["torque_nm"] == 300
    assert row["zero_to_100_kmh_s"] == 7.3
    assert row["fuel_type"] == "Petrol"


def test_ultimatespecs_parser_keeps_missing_fields_nullable():
    html = """
    <html><head><title>Mercedes Benz W206 Class C 200 2021 2024 Specs</title></head>
    <body><h1>Mercedes Benz W206 Class C 200 2021 2024 Specs</h1>
    <table><tr><th>Engine Type</th><td>Inline 4</td></tr></table>
    </body></html>
    """
    row = UltimateSpecsExtractor().extract_detail(
        html,
        source_url="https://www.ultimatespecs.com/fixture/missing",
    )

    assert row is not None
    assert row["engine_type"] == "Inline 4"
    assert row["engine_cc"] is None
    assert row["top_speed_kmh"] is None
    assert row["torque_nm"] is None


def test_ultimatespecs_parser_handles_real_detail_label_style():
    html = """
    <html><body>
    <h1>Mercedes Benz Class C (W206) 200 9G-TRONIC Specs</h1>
    <p>(2024 - present) - Technical Specifications</p>
    <div>Engine type - Number of cylinders : Inline 4</div>
    <div>Fuel type : Mild Hybrid / Petrol</div>
    <div>Engine displacement : 1496 cm3 / 91.3 cu-in</div>
    <div>Aspiration : Turbo Intercooler</div>
    <div>Maximum torque : 300 Nm / 221 lb-ft</div>
    <div>Transmission Gearbox - Number of speeds :</div>
    <div>9 speed Automatic</div>
    <div>Top Speed : 246 km/h / 153 Mph</div>
    <div>Acceleration 0 to 100 km/h (0 to 62 mph) : 7.3 s</div>
    <div>Num. of Doors : 4 doors</div>
    <div>Num. of Seats : 5 seats</div>
    <div>Trunk / Boot capacity : 455 L / 16.1 cu-ft</div>
    <div>Front Brakes - Disc dimensions : Vented Discs</div>
    <div>Rear Brakes - Disc dimensions : Discs</div>
    <div>Front Suspension : Independent. MacPherson.</div>
    <div>Rear Suspension : Multi-link.</div>
    </body></html>
    """
    row = UltimateSpecsExtractor().extract_detail(
        html,
        source_url="https://www.ultimatespecs.com/fixture/real-style",
    )

    assert row is not None
    assert row["variant"] == "C200 9G-TRONIC"
    assert row["year_start"] == 2024
    assert row["engine_type"] == "Inline 4"
    assert row["fuel_type"] == "Mild Hybrid / Petrol"
    assert row["engine_cc"] == 1496
    assert row["engine_aspiration"] == "Turbo Intercooler"
    assert row["torque_nm"] == 300
    assert row["transmission"] == "9 speed Automatic"
    assert row["number_of_gears"] == 9
    assert row["top_speed_kmh"] == 246
    assert row["zero_to_100_kmh_s"] == 7.3
    assert row["number_of_doors"] == 4
    assert row["seat_capacity"] == 5
    assert row["boot_space_litres"] == 455
    assert row["front_brakes"] == "Vented Discs"
    assert row["rear_brakes"] == "Discs"
    assert row["front_suspension"] == "Independent. MacPherson."
    assert row["rear_suspension"] == "Multi-link."


def test_ultimatespecs_parser_handles_w204_2011_sedan_title_variant_and_year_range():
    html = """
    <html><body>
    <h1>Mercedes Benz C Class (W204 2011) Sedan 200 BlueEFFICIENCY Aut. Specs</h1>
    <div>Engine type - Number of cylinders : Inline 4</div>
    </body></html>
    """
    row = UltimateSpecsExtractor().extract_detail(
        html,
        source_url="https://www.ultimatespecs.com/fixture/w204-2011",
    )

    assert row is not None
    assert row["variant"] == "C200"
    assert row["year_start"] == 2011
    assert row["year_end"] == 2014


def test_ultimatespecs_parser_applies_generation_year_fallback_for_w204_and_w205():
    extractor = UltimateSpecsExtractor()
    w204 = extractor.extract_detail(
        "<html><body><h1>Mercedes Benz W204 Class C 200 Kompressor Specs</h1></body></html>",
        source_url="https://www.ultimatespecs.com/fixture/w204",
    )
    w205 = extractor.extract_detail(
        "<html><body><h1>Mercedes Benz W205 Class C 200 Specs</h1></body></html>",
        source_url="https://www.ultimatespecs.com/fixture/w205",
    )

    assert w204 is not None
    assert w204["year_start"] == 2007
    assert w204["year_end"] == 2011
    assert w205 is not None
    assert w205["year_start"] == 2014
    assert w205["year_end"] == 2018


def test_ultimatespecs_generation_fixture_extracts_only_c200_detail_links():
    html = (FIXTURES / "ultimatespecs_w206_generation.html").read_text(encoding="utf-8")
    links = UltimateSpecsExtractor().extract_c200_detail_links(
        html,
        source_url="https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M11849/Class-C-(W206)",
    )

    assert links == [
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/12345/Mercedes-Benz-W206-Class-C-200.html",
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/12346/Mercedes-Benz-W206-Class-C-200-4MATIC.html",
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/12347/Mercedes-Benz-W206-Class-C-200-9G-TRONIC.html",
    ]


def test_ultimatespecs_approved_generation_urls_cover_w204_w205_w206():
    assert _is_approved_generation_url(
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M484/W204-Class-C"
    )
    assert _is_approved_generation_url(
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M3552/C-Class-%28W204-2011%29-Sedan"
    )
    assert _is_approved_generation_url(
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M7349/W205-Class-C"
    )
    assert _is_approved_generation_url(
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M9956/Class-C-%28W205-2019%29"
    )
    assert _is_approved_generation_url(
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M11849/Class-C-%28W206%29"
    )


def test_ultimatespecs_live_generation_fetches_extracted_detail_urls_only(tmp_path):
    generation_url = (
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M11849/"
        "Class-C-(W206)#pluginhybrid_engines"
    )
    generation_html = (FIXTURES / "ultimatespecs_w206_generation.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES / "ultimatespecs_c200_detail.html").read_text(encoding="utf-8")
    detail_urls = UltimateSpecsExtractor().extract_c200_detail_links(
        generation_html,
        source_url=generation_url,
    )

    class FakeFetcher:
        last_error = ""

        def __init__(self):
            self.urls = []

        def fetch(self, url: str) -> str:
            self.urls.append(url)
            if url == generation_url:
                return generation_html
            if url in detail_urls:
                return detail_html.replace("Class C 200", "Class C 200 4MATIC")
            raise AssertionError(f"Unexpected fetch: {url}")

    fetcher = FakeFetcher()
    session = _session(tmp_path)
    try:
        summary = run(
            session,
            use_fixtures=False,
            use_network=True,
            model="c200",
            url=generation_url,
            fetcher=fetcher,
        )

        assert summary.status == "ok"
        assert summary.fetched == 3
        assert summary.stored == 3
        assert session.query(VehicleSpec).count() == 3
    finally:
        session.close()

    assert fetcher.urls == [generation_url] + detail_urls


def test_ultimatespecs_live_reports_blocked_by_robots_for_generation_url(tmp_path):
    class BlockingFetcher:
        def fetch(self, url: str) -> str:
            raise ValueError(f"robots.txt disallows fetching {url}")

    session = _session(tmp_path)
    try:
        summary = run(
            session,
            use_fixtures=False,
            use_network=True,
            url="https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M11849/Class-C-(W206)",
            fetcher=BlockingFetcher(),
        )
    finally:
        session.close()

    assert summary.status == "blocked_by_robots"
    assert "robots.txt disallows" in summary.error


def test_ultimatespecs_live_reports_fetch_failed_for_generation_url(tmp_path):
    class EmptyFetcher:
        last_error = "HTTP 403"

        def fetch(self, url: str) -> str:
            return ""

    session = _session(tmp_path)
    try:
        summary = run(
            session,
            use_fixtures=False,
            use_network=True,
            url="https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M11849/Class-C-(W206)",
            fetcher=EmptyFetcher(),
        )
    finally:
        session.close()

    assert summary.status == "fetch_failed"
    assert summary.error == "HTTP 403"


def test_ultimatespecs_fixture_ingest_writes_vehicle_specs_not_training_data(tmp_path):
    session = _session(tmp_path)
    try:
        session.add(
            TrainingData(
                model="C_CLASS",
                year=2021,
                age=5,
                price_rm=180000,
                transmission="Automatic",
                mileage=25000,
                fuel_type="Petrol",
                tax=150.0,
                mpg=40.0,
                engine_size=1.5,
            )
        )
        session.commit()
        before_training_count = session.query(TrainingData).count()

        summary = run(session, use_fixtures=True, use_network=False)

        assert summary.status == "ok"
        assert summary.stored == 1
        assert session.query(VehicleSpec).count() == 1
        assert session.query(TrainingData).count() == before_training_count
    finally:
        session.close()


def test_ultimatespecs_live_without_approved_url_stops_before_fetch(tmp_path):
    session = _session(tmp_path)
    try:
        summary = run(session, use_fixtures=False, use_network=True, model="c200")
    finally:
        session.close()

    assert summary.status == "not_configured"
    assert summary.fetched == 0
    assert summary.stored == 0
