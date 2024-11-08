"""
Design pattern for managing the instantiation, teardown, and dependency resolution of global objects
(loggers, database connections, etc.).
"""
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type, Optional, Callable, TypeVar, Generator

import networkx as nx

T_GlobalObject = TypeVar('T_GlobalObject', bound='GlobalObject')


class GlobalObject:
    """
    Base class for global objects.
    """

    def __init__(self, get_fn: Optional[Callable[[], Any]] = None):
        """
        Initialize the global object.
        :param get_fn: Custom function to return the global object
        """
        self.get_fn = get_fn

    def setup(self) -> None:
        """
        Setup method for the global object.
        """
        pass

    def teardown(self) -> None:
        """
        Teardown method for the global object.
        """
        pass

    @classmethod
    def param_name(cls) -> Optional[str]:
        # convert camel case to snake case
        return re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()


class GlobalObjectProxy(GlobalObject, ABC):
    """
    Proxy class for global object instances.
    """

    def __init__(self):
        super().__init__()
        self._instance: Optional[Any] = None

    @abstractmethod
    def _setup_proxy_impl(self) -> None:
        """
        Setup method for the global object.
        """
        pass

    def _teardown_proxy_impl(self) -> None:
        """
        Teardown method for the global object.
        """
        del self._instance

    def teardown(self) -> None:
        """
        Teardown method for the global object.
        """
        self._teardown_proxy_impl()

    def setup(self) -> None:
        """
        Setup method for the global object.
        """
        self._setup_proxy_impl()

        if self._instance is None:
            raise RuntimeError("The `_instance` attribute must be set in the `_setup_proxy_impl` method.")

    def __getattr__(self, item: str) -> Any:
        """
        Delegate attribute access to the wrapped instance.
        :param item: attribute name
        :return: property of the wrapped instance
        """
        # Python will merge the __dict__ of the proxy and the wrapped instance
        return getattr(self._instance, item)

    def __getitem__(self, item: Any) -> Any:
        """
        Delegate item access to the wrapped instance.
        :param item: item name
        :return: property of the wrapped instance
        """
        return self._instance[item]


class GlobalObjectManager:
    """
    Manage the lifecycle of global objects.

      Usage:

    ```python
    @register_global_object()
    class Config(GlobalObject):
        def setup(self) -> None:
            self.data = {"api_key": "secret"}

    @register_global_object(dependencies=[Config])
    class APIClient(GlobalObject):
        def __init__(self, config: Config):
            self.config = config

        def setup(self) -> None:
            self.client = f"API Client with key: {self.config.data['api_key']}"

    # Initialize global objects
    global_manager.startup()

    # Use global objects
    api_client = global_manager.get(APIClient)
    print(api_client.client)  # Output: API Client with key: secret

    # Clean up
    global_manager.shutdown()
    ```
    """

    def __init__(self):
        self._instances: Dict[T_GlobalObject, GlobalObject] = {}
        self._dependencies: Dict[T_GlobalObject, List[T_GlobalObject]] = {}
        self._dependency_graph = nx.DiGraph()

    def register(self, cls: T_GlobalObject = None, dependencies: Optional[List[T_GlobalObject]] = None) -> \
            Callable[[T_GlobalObject], T_GlobalObject]:
        """
        Decorator to register a class as a global object.

        :param cls: The class to be registered.
        :param dependencies: List of other global object classes this class depends on.
        :return: The original class or a wrapper function if called without arguments.
        """

        def decorator(c: T_GlobalObject) -> T_GlobalObject:
            self._instances[c] = None
            self._dependencies[c] = dependencies or []

            # Update dependency graph
            self._dependency_graph.add_node(c)
            for dep in self._dependencies[c]:
                self._dependency_graph.add_edge(dep, c)

            # Check for circular dependencies
            if not nx.is_directed_acyclic_graph(self._dependency_graph):
                raise ValueError(f"Circular dependency detected when registering {c.__name__}")

            return c

        if cls is None:
            return decorator
        return decorator(cls)

    def _get_instance(self, cls: T_GlobalObject) -> GlobalObject:
        """
        Get or create an instance of a registered class.

        :param cls: The class to instantiate.
        :return: An instance of the requested class.
        :raises RuntimeError: If the class is not registered.
        """
        if cls not in self._instances:
            raise RuntimeError(f"{cls.__name__} is not registered.")

        if self._instances[cls] is None:
            # Instantiate dependencies first
            dep_instances = {}
            for dep in self._dependencies[cls]:
                # Skip dependencies that don't have a param name from injection (e.g. logger)
                dep_instance = self._get_instance(dep)
                if (param_name := dep.param_name()) is None:
                    continue
                dep_instances[param_name] = dep_instance

            # Instantiate the class
            try:
                self._instances[cls] = cls(**dep_instances)
                self._instances[cls].setup()
            except TypeError as t:
                raise RuntimeError(f"Failed to instantiate {cls.__name__}") from t

        return self._instances[cls]

    def get(self, cls: T_GlobalObject) -> GlobalObject:
        """
        Get a global object instance.

        :param cls: The class to get an instance of.
        :return: The instance of the requested class.
        """
        instance = self._get_instance(cls)
        if instance.get_fn is not None:
            return instance.get_fn()
        return instance

    def startup(self) -> None:
        """
        Initialize all registered global objects in dependency order.
        """
        for cls in nx.topological_sort(self._dependency_graph):
            self._get_instance(cls)

    def shutdown(self) -> None:
        """
        Teardown all initialized global objects in reverse dependency order.
        """
        for cls in reversed(list(nx.topological_sort(self._dependency_graph))):
            if self._instances[cls] is not None:
                self._instances[cls].teardown()
                self._instances[cls] = None

    def depends(self, cls: T_GlobalObject) -> 'Depends':
        """
        Create a FastAPI dependency for a global object.

        :param cls: The class to create a dependency for.
        :return: A FastAPI Depends object that can be used as a dependency.

        Usage:
        ```python
        from fastapi import FastAPI, Depends
        from your_module import GlobalObjectManager, register_global_object, GlobalObject

        global_manager = GlobalObjectManager()

        @register_global_object()
        class DatabaseClient(GlobalObject):
            def setup(self) -> None:
                self.connection = "DB Connection"

            def query(self, sql: str) -> str:
                return f"Result for {sql}"

        app = FastAPI()

        @app.on_event("startup")
        async def startup_event():
            global_manager.startup()

        @app.on_event("shutdown")
        async def shutdown_event():
            global_manager.shutdown()

        @app.get("/query")
        async def perform_query(
            db: DatabaseClient = Depends(global_manager.get_dependency(DatabaseClient))
        ):
            result = db.query("SELECT * FROM users")
            return {"result": result}
        ```
        """
        from fastapi import Depends

        instance = self._get_instance(cls)

        if instance.get_fn is not None:
            return Depends(instance.get_fn)

        return Depends(lambda: instance)


# Create a global instance of the manager
global_manager = GlobalObjectManager()


def register_global_object(dependencies: Optional[List[Any]] = None) -> Callable[
    [T_GlobalObject], T_GlobalObject]:
    """
    Decorator to register a class as a global object.

    :param dependencies: List of other global object classes this class depends on.
    :return: A decorator function.
    """

    def decorator(cls: T_GlobalObject) -> T_GlobalObject:
        return global_manager.register(cls, dependencies)

    return decorator
