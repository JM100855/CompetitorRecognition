from app.db.session import SessionLocal, init_db
from app.schemas.domain import CompanyCreate, NicheCreate, SourceCreate
from app.services.store import create_company, create_niche, create_source


def main() -> None:
    init_db()
    with SessionLocal() as db:
        niche = create_niche(
            db,
            NicheCreate(
                name="Sales software",
                description="Track changes across pricing, product, and hiring pages.",
            ),
        )
        company = create_company(
            db,
            niche.id,
            CompanyCreate(name="Example Company", domain="example.com", notes="Replace this with a real company."),
        )
        create_source(
            db,
            company.id,
            SourceCreate(page_type="homepage", url="https://example.com"),
        )


if __name__ == "__main__":
    main()
