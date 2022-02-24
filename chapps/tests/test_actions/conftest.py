"""Test fixtures for action object testing"""
import pytest
from pytest import fixture
from chapps.actions import PostfixActions, PostfixOQPActions, PostfixGRLActions, PostfixSPFActions

@fixture
def postfix_actions():
    return PostfixActions()

@fixture
def oqp_actions():
    return PostfixOQPActions()

@fixture
def grl_actions():
    return PostfixGRLActions()

@fixture
def spf_actions():
    return PostfixSPFActions()

@fixture
def spf_reason():
    return "mock SPF explanation"
