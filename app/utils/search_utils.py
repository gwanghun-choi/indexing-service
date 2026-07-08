"""
검색 관련 유틸리티 함수
"""

from typing import Any, Dict, List


def calculate_search_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    검색 결과로부터 통계 계산
    
    Args:
        results: 검색 결과 리스트
            - filename: 파일명
            - score: 유사도 점수
    
    Returns:
        Dict: 통계 정보
            - total_results: 총 검색 결과 수
            - documents_found: 검색된 문서 개수
            - document_distribution: 문서별 결과 개수 (filename: count)
            - similarity_distribution: 문서별 유사도 분포 (filename: {high/medium/low: count})
            - average_score: 평균 유사도 점수
            - max_score: 최고 유사도 점수
            - min_score: 최저 유사도 점수
    """
    if not results:
        return {
            "total_results": 0,
            "documents_found": 0,
            "document_distribution": {},
            "similarity_distribution": {},
            "average_score": 0.0,
            "max_score": 0.0,
            "min_score": 0.0,
        }
    
    # 문서별 결과 개수 계산
    doc_distribution = {}
    for result in results:
        filename = result["filename"]
        if filename in doc_distribution:
            doc_distribution[filename] += 1
        else:
            doc_distribution[filename] = 1
    
    # 유사도 점수 추출
    scores = [result["score"] for result in results]
    
    # 문서별 유사도 분포 계산
    # 높음: >= 0.825 (82.5%), 보통: 0.80 ~ 0.825, 낮음: < 0.80
    similarity_distribution = {}
    
    for result in results:
        filename = result["filename"]
        score = result["score"]
        
        # 문서별 유사도 카운터 초기화
        if filename not in similarity_distribution:
            similarity_distribution[filename] = {"high": 0, "medium": 0, "low": 0}
        
        # 유사도 등급 분류
        if score >= 0.825:
            similarity_distribution[filename]["high"] += 1
        elif score >= 0.80:
            similarity_distribution[filename]["medium"] += 1
        else:
            similarity_distribution[filename]["low"] += 1
    
    return {
        "total_results": len(results),
        "documents_found": len(doc_distribution),
        "document_distribution": doc_distribution,
        "similarity_distribution": similarity_distribution,
        "average_score": round(sum(scores) / len(scores), 4),
        "max_score": round(max(scores), 4),
        "min_score": round(min(scores), 4),
    }






