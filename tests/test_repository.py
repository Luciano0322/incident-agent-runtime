from app.db.repositories import IncidentRepository
from app.db.session import create_sessionmaker
from app.schemas.investigation import InvestigationResult, ToolCallRecord
from app.schemas.report import InvestigationReport
from tests.scenarios import CHECKOUT, CHECKOUT_LINES, POOL_REPORT

RESULT = InvestigationResult(
    report=InvestigationReport.model_validate(POOL_REPORT),
    evidence=CHECKOUT_LINES,
    tool_calls=[ToolCallRecord(name="query_logs", args={"service": "checkout", "keyword": None})],
)


async def test_repeated_investigations_keep_every_report(settings, database):
    sessionmaker = create_sessionmaker(settings)
    async with sessionmaker() as session, session.begin():
        incident = await IncidentRepository(session).create(CHECKOUT.title, CHECKOUT.description)
        incident_id = incident.id

    saved_ids = []
    for _ in range(2):
        async with sessionmaker() as session, session.begin():
            record = await IncidentRepository(session).save_report(incident_id, RESULT, "test-model")
            saved_ids.append(record.id)

    async with sessionmaker() as session:
        reports = await IncidentRepository(session).list_reports(incident_id)
    await sessionmaker.kw["bind"].dispose()

    assert [report.id for report in reports] == saved_ids
