import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.university import BuildingCreate, FacultyCreate, GroupCreate, RoomCreate, SubjectCreate, TeacherCreate, UniversityCreate, UniversityUpdate
from app.services.university_service import UniversityService


@pytest.mark.asyncio
async def test_university_crud_operations(db_session: AsyncSession):
    # 1. Create
    payload = UniversityCreate(name="O'zbekiston Milliy Universiteti", short_name="O'zMU", city="Toshkent")
    univ = await UniversityService.create_university(db_session, payload)
    assert univ.id is not None
    assert univ.name == "O'zbekiston Milliy Universiteti"

    # 2. Get
    fetched = await UniversityService.get_university_by_id(db_session, univ.id)
    assert fetched is not None
    assert fetched.short_name == "O'zMU"

    # 3. Update
    upd_payload = UniversityUpdate(short_name="NUU", city="Tashkent")
    updated = await UniversityService.update_university(db_session, univ.id, upd_payload)
    assert updated.short_name == "NUU"
    assert updated.city == "Tashkent"

    # 4. Faculty and Group creation
    fac = await UniversityService.create_faculty(db_session, FacultyCreate(name="Matematika fakulteti", university_id=univ.id))
    assert fac.id is not None

    grp = await UniversityService.create_group(db_session, GroupCreate(name="MATH-201", university_id=univ.id, faculty_id=fac.id, course_number=2))
    assert grp.id is not None
    assert grp.name == "MATH-201"

    # 5. Building, Room, Subject, Teacher
    bld = await UniversityService.create_building(db_session, BuildingCreate(name="Asosiy bino", university_id=univ.id))
    room = await UniversityService.create_room(db_session, RoomCreate(number="101", building_id=bld.id, capacity=50))
    subj = await UniversityService.create_subject(db_session, SubjectCreate(name="Matematik analiz", university_id=univ.id))
    tchr = await UniversityService.create_teacher(db_session, TeacherCreate(full_name="Prof. Olimov", university_id=univ.id))

    assert bld.id is not None
    assert room.id is not None
    assert subj.id is not None
    assert tchr.id is not None

    # 6. Delete
    deleted = await UniversityService.delete_university(db_session, univ.id)
    assert deleted is True
    assert await UniversityService.get_university_by_id(db_session, univ.id) is None
