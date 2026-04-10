# Movie Night Recommender

A production-quality movie recommendation application built with Python and Streamlit.

## Features

- User authentication with secure password hashing
- Onboarding process to learn user preferences
- Personalized movie recommendations using hybrid system (content-based, collaborative filtering, popularity)
- Semantic search using vector embeddings
- Group recommendations for movie nights with friends
- Modern UI with Netflix-style cards and smooth animations
- TMDB API integration for movie data

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file (copy from `.env.example`) and set `TMDB_API_KEY`.
3. Run the application:
   ```
   streamlit run app.py
   ```

## Project Structure

- `app.py`: Main application entry point
- `pages/`: Streamlit pages for different sections
- `components/`: Reusable UI components
- `recommender/`: Recommendation algorithms
- `semantic_search/`: Vector search functionality
- `database/`: Database models and setup
- `services/`: External API integrations
- `assets/`: CSS and static files

## Technologies Used

- **Frontend**: Streamlit, streamlit-extras
- **Backend**: Python
- **Database**: SQLite with SQLAlchemy
- **ML/AI**: scikit-learn, Surprise, sentence-transformers, FAISS
- **APIs**: TMDB API

## Usage

1. Register or login
2. Complete onboarding by selecting genres and liked movies
3. Explore personalized recommendations on the home page
4. Rate movies to improve recommendations
5. Create groups for shared movie recommendations
6. Use the search bar for semantic movie search
