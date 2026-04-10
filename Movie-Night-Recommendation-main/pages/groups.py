import streamlit as st

from components.movie_card import movie_card
from database.db import SessionLocal, sync_movies
from database.models import Group, GroupMember, GroupRating
from recommender.hybrid import get_group_recommendations
from services.tmdb_api import get_trending_movies


def _get_user_groups(db, user_id):
    return (
        db.query(Group)
        .join(GroupMember, Group.group_id == GroupMember.group_id)
        .filter(GroupMember.user_id == user_id)
        .order_by(Group.created_at.desc())
        .all()
    )


def groups_page():
    if "user" not in st.session_state:
        st.error("Please login first")
        return

    user = st.session_state.user
    st.markdown('<div class="rate-page-title compact">Watch With Friends</div>', unsafe_allow_html=True)

    tab_my_groups, tab_create, tab_join = st.tabs(["My Groups", "Create Group", "Join Group"])

    with tab_my_groups:
        db = SessionLocal()
        groups = _get_user_groups(db, user.user_id)

        if not groups:
            st.info("You have not joined any groups yet.")
        else:
            group_names = {group.group_name: group.group_id for group in groups}
            selected_group_name = st.selectbox("Choose a group", list(group_names.keys()), key="selected_group")
            selected_group_id = group_names[selected_group_name]

            st.subheader(selected_group_name)
            recommendations = get_group_recommendations(selected_group_id, top_n=8)
            if not recommendations:
                st.info("Not enough shared taste data yet. Ask members to rate more movies.")
            else:
                cols = st.columns(4)
                for index, item in enumerate(recommendations):
                    movie = item["movie"]
                    with cols[index % 4]:
                        movie_card(
                            {
                                "id": movie.movie_id,
                                "title": movie.title,
                                "overview": movie.overview,
                                "poster_path": movie.poster_path,
                                "vote_average": movie.vote_average,
                            },
                            key_suffix=f"group_{selected_group_id}_{index}",
                            explanation=item["explanation"],
                            badge="Group Pick",
                        )

                st.markdown("#### Rate a movie for the group")
                trending_movies = get_trending_movies(limit=6)
                if trending_movies:
                    sync_movies(db, trending_movies)
                    rating_cols = st.columns(3)
                    for index, movie in enumerate(trending_movies[:6]):
                        with rating_cols[index % 3]:
                            st.markdown(f"**{movie['title']}**")
                            group_rating = st.slider(
                                "Group rating",
                                min_value=1,
                                max_value=5,
                                value=3,
                                key=f"group_rating_{selected_group_id}_{movie['id']}",
                            )
                            if st.button(
                                "Save Group Rating",
                                key=f"save_group_rating_{selected_group_id}_{movie['id']}",
                                use_container_width=True,
                            ):
                                existing = db.query(GroupRating).filter(
                                    GroupRating.group_id == selected_group_id,
                                    GroupRating.movie_id == movie["id"],
                                ).first()
                                if existing:
                                    existing.rating = float(group_rating)
                                else:
                                    db.add(
                                        GroupRating(
                                            group_id=selected_group_id,
                                            movie_id=movie["id"],
                                            rating=float(group_rating),
                                        )
                                    )
                                db.commit()
                                st.success("Group rating saved.")
                                st.rerun()

        db.close()

    with tab_create:
        group_name = st.text_input("Group Name", key="create_group_name")
        if st.button("Create Group", key="create_group_btn"):
            if not group_name.strip():
                st.warning("Enter a group name.")
            else:
                db = SessionLocal()
                existing = db.query(Group).filter(Group.group_name == group_name.strip()).first()
                if existing:
                    st.error("A group with this name already exists.")
                else:
                    new_group = Group(group_name=group_name.strip(), created_by=user.user_id)
                    db.add(new_group)
                    db.commit()
                    db.add(GroupMember(group_id=new_group.group_id, user_id=user.user_id))
                    db.commit()
                    st.success("Group created.")
                db.close()

    with tab_join:
        join_name = st.text_input("Enter group name to join", key="join_group_name")
        if st.button("Join Group", key="join_group_btn"):
            if not join_name.strip():
                st.warning("Enter a group name.")
            else:
                db = SessionLocal()
                group = db.query(Group).filter(Group.group_name == join_name.strip()).first()
                if not group:
                    st.error("Group not found.")
                else:
                    existing_member = db.query(GroupMember).filter(
                        GroupMember.group_id == group.group_id,
                        GroupMember.user_id == user.user_id,
                    ).first()
                    if existing_member:
                        st.info("You are already a member of this group.")
                    else:
                        db.add(GroupMember(group_id=group.group_id, user_id=user.user_id))
                        db.commit()
                        st.success(f"You joined {group.group_name}.")
                db.close()
