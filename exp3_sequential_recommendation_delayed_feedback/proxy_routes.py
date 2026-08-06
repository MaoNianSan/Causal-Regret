"""Compatibility facade for Exp3 route features, selection, and fitting."""
from ridge_features import _design_matrix, _make_features, design_matrix, make_feature_frames
from ridge_selection import RidgeSelection, select_ridge_alpha
from route_fitting import FittedRoutes, _history_mean_scores, fit_routes, history_mean_scores


fit_proxy_routes = fit_routes

__all__ = [
    "FittedRoutes",
    "RidgeSelection",
    "_design_matrix",
    "_history_mean_scores",
    "_make_features",
    "design_matrix",
    "fit_proxy_routes",
    "fit_routes",
    "history_mean_scores",
    "make_feature_frames",
    "select_ridge_alpha",
]
