.PHONY: test setup shell coverage publish-build publish-clean release

test:
	uv run pytest

setup:
	uv sync --dev

shell:
	uv shell

coverage:
	uv run pytest --cov=codoc --cov-report=term-missing

publish-build:
	uv run hatch build

publish-clean:
	rm -rf dist/

# Release: tag the current version and push to trigger CI publish.
# CI workflow: .github/workflows/publish.yml (on tag push v*)
release:
	@VERSION=$$(grep -E "^__version__" codoc/__version__.py | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/"); \
	echo "Releasing v$$VERSION"; \
	git tag "v$$VERSION"; \
	git push origin "v$$VERSION"
