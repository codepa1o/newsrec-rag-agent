from app.core.sample_data import sample_articles, sample_behaviors
from app.services.embedding import HashingEmbeddingProvider
from app.services.profile import ProfileService
from app.services.recommender import NewsRecommender


def test_recommendations_are_non_empty_and_exclude_clicked_items():
    articles = sample_articles()
    profile_service = ProfileService(articles, sample_behaviors())
    recommender = NewsRecommender(articles, profile_service, HashingEmbeddingProvider())

    recommendations = recommender.recommend("U100", top_k=5)
    recommended_ids = {item.news_id for item in recommendations}

    assert recommendations
    assert "N1001" not in recommended_ids
    assert "N1002" not in recommended_ids
    assert all(item.reason for item in recommendations)


def test_search_supports_category_filter():
    articles = sample_articles()
    profile_service = ProfileService(articles, sample_behaviors())
    recommender = NewsRecommender(articles, profile_service, HashingEmbeddingProvider())

    results = recommender.search("AI 检索", top_k=5, filters={"category": "科技"})

    assert results
    assert all(item.category == "科技" for item in results)
