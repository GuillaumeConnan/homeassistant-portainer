"""Test container processing performance with large datasets."""

import pytest
import time
from unittest.mock import Mock, patch

from custom_components.portainer.coordinator import PortainerCoordinator


class TestContainerPerformance:
    """Test container processing with large numbers of containers."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = Mock()
        hass.async_add_executor_job = Mock(return_value=[])
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create mock config entry."""
        config_entry = Mock()
        config_entry.entry_id = "test_entry_id"
        config_entry.data = {
            "name": "Test Portainer",
            "host": "localhost:9000",
            "api_key": "test_api_key",
            "ssl": False,
            "verify_ssl": True,
        }
        config_entry.options = {
            "containers": []
        }  # Select all containers for performance test
        return config_entry

    @pytest.fixture
    def coordinator(self, mock_hass, mock_config_entry):
        """Create coordinator for testing."""
        with patch("custom_components.portainer.coordinator.PortainerAPI"):
            coordinator = PortainerCoordinator(mock_hass, mock_config_entry)
            coordinator.raw_data = {
                "endpoints": {"1": {"Status": 1, "Name": "test-endpoint"}},
                "containers": {"1": {}},
            }
            return coordinator

    def test_large_number_of_containers_processing(self, coordinator):
        """Test processing performance with 1000+ containers."""
        # Generate large container dataset
        num_containers = 1000
        large_container_list = []

        for i in range(num_containers):
            large_container_list.append(
                {
                    "Id": f"container_{i}",
                    "Names": [f"/test-container-{i}"],
                    "State": "running",
                    "Image": f"test-image:{i % 10}",
                }
            )
        coordinator.selected_containers = {
            f"test_entry_id_1_test-container-{i}" for i in range(num_containers)
        }

        def mock_inspect(url):
            container_id = url.split("/")[-2]
            return {
                "Id": container_id,
                "State": {"Status": "running"},
                "HostConfig": {"NetworkMode": "bridge"},
                "NetworkSettings": {"Networks": {}},
                "Mounts": [],
                "Image": f"test-image:{container_id.split('_')[1]}",
            }

        # Mock API responses
        inspect_calls = 0

        def mock_query_side_effect(*args, **kwargs):
            nonlocal inspect_calls
            if "containers/json" in args[0]:
                return large_container_list
            else:
                # Inspect call
                inspect_calls += 1
                return mock_inspect(args[0])

        with patch.object(coordinator.api, "query", side_effect=mock_query_side_effect):
            start_time = time.time()
            coordinator.get_containers()
            end_time = time.time()

            processing_time = end_time - start_time

            # Should process all containers within reasonable time (adjust threshold as needed)
            assert processing_time < 30.0  # Should complete within 30 seconds

            # Should have processed all containers
            flat_containers = coordinator.raw_data["containers"]
            assert len(flat_containers) == num_containers

            print(
                f"Processed {num_containers} containers in {processing_time:.2f} seconds"
            )

    def test_memory_usage_with_large_datasets(self, coordinator):
        """Test memory usage doesn't grow excessively with large datasets."""
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Generate moderately large dataset
        num_containers = 500
        large_container_list = []

        for i in range(num_containers):
            large_container_list.append(
                {
                    "Id": f"container_{i}",
                    "Names": [f"/test-container-{i}"],
                    "State": "running",
                    "Image": "test-image:latest",
                }
            )
        coordinator.selected_containers = {
            f"test_entry_id_1_test-container-{i}" for i in range(num_containers)
        }

        def mock_inspect(url):
            return {
                "Id": url.split("/")[-2],
                "State": {"Status": "running"},
                "HostConfig": {"NetworkMode": "bridge"},
                "NetworkSettings": {"Networks": {}},
                "Mounts": [],
                "Image": "test-image:latest",
            }

        def query_side_effect(url, *args, **kwargs):
            if "containers/json" in url:
                return large_container_list
            return mock_inspect(url)

        with patch.object(coordinator.api, "query", side_effect=query_side_effect):
            coordinator.get_containers()

            # Get final memory usage
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            # Memory increase should be reasonable (adjust threshold as needed)
            assert memory_increase < 100  # Should use less than 100MB additional memory

            print(
                f"Memory increase: {memory_increase:.2f} MB for {num_containers} containers"
            )

    def test_container_processing_timeout_handling(self, coordinator):
        """Test timeout handling during container processing."""
        # Create containers that take time to process
        slow_containers = []
        num_containers = 100

        for i in range(num_containers):
            slow_containers.append(
                {
                    "Id": f"container_{i}",
                    "Names": [f"/slow-container-{i}"],
                    "State": "running",
                }
            )
        coordinator.selected_containers = {
            f"test_entry_id_1_slow-container-{i}" for i in range(num_containers)
        }

        def slow_inspect(url):
            time.sleep(0.01)  # Simulate slow API response
            return {
                "Id": url.split("/")[-2],
                "State": {"Status": "running"},
                "HostConfig": {"NetworkMode": "bridge"},
                "NetworkSettings": {"Networks": {}},
                "Mounts": [],
                "Image": "test-image:latest",
            }

        def query_side_effect(url, *args, **kwargs):
            if "containers/json" in url:
                return slow_containers
            return slow_inspect(url)

        with patch.object(coordinator.api, "query", side_effect=query_side_effect):
            start_time = time.time()
            coordinator.get_containers()
            end_time = time.time()

            processing_time = end_time - start_time

            # Should complete within reasonable time even with slow responses
            assert processing_time < 10.0  # Should complete within 10 seconds
            assert len(coordinator.raw_data["containers"]) == num_containers
