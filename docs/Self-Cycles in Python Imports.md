Understanding Self-Cycles in Python Imports
What is a “self-cycle”? In Python, a circular import happens when two (or more) modules depend on each other in a loop. For example, module A imports from module B, and B (directly or indirectly) imports from A. A self-cycle is a special case where a module (or package) ends up importing itself. In effect, the import chain starts and ends at the same module. An architecture analysis of the framework even flagged a “Discovery Self-Cycle” with the note “Module importing itself”[1]. In practical terms, this often arises from a package’s __init__.py inadvertently re-importing the package or one of its own submodules.
When Python imports a module, it executes the code in that module top-to-bottom. If during this process module A needs module B, Python pauses A, loads B, and then resumes A. A circular import means while loading B, Python tries to import A again, but A hasn’t finished loading yet. The result is that A is partially initialized, so B cannot reliably import what it needs from A. This leads to errors like:
ImportError: cannot import name 'X' from partially initialized module 'A' (most likely due to a circular import)
In other words, neither module can complete its setup because each is waiting on the other[2]. A self-cycle is simply the same problem where the “other” module is really the same module (or package) re-entered.
Why are circular/self-cycles problematic? Besides immediate import errors, they indicate poor modular design and cause several hidden issues. Circular dependencies make code harder to understand and maintain: the flow of imports becomes tangled, confusing developers[3]. Debugging such problems is notoriously difficult, since tracebacks bounce between modules (you may even see the same module listed multiple times)[4][3]. Performance can suffer too, because Python may reload or re-execute modules multiple times during a circular import, slowing startup[5]. In large codebases they also hinder portability and reuse, and they violate principles like separation of concerns[6]. In short, import cycles (including self-cycles) are considered a “code smell” and an architectural design issue that should be fixed[7].
How Self-Cycles Happened in Our Case
Our analysis of the codebase found two self-cycles: one in framework.discovery and another in framework.ml.feature_store[1]. This means each of those packages ended up importing itself. The fix suggestions were:
	•	Discovery package: “Split discovery into core and extensions”[1].
	•	Feature Store package: “Separate feature store interface from implementation”[8].
These hints point to the root causes: monolithic __init__.py files and ambiguous module naming.
Case Study: framework.discovery
The internal import analysis shows that marty_msf.framework.discovery lists itself in its own imports and imports-by lists[9]. For example, the JSON has:
"marty_msf.framework.discovery": {    "imports": [        "marty_msf.framework.core",        "...",        "marty_msf.framework.discovery",  // <--- self-cycle        ...    ],    "imported_by": [        "marty_msf.framework.discovery",  // <--- self referenced again        "marty_msf.framework.plugins"    ]}
This confirms framework.discovery is importing itself. In practice, this likely came from a line in framework/discovery/__init__.py (or a submodule) like:
# Hypothetical problematic code in framework/discovery/__init__.pyfrom marty_msf.framework.discovery.core import DiscoveryCore# or maybefrom . import DiscoveryCore
If, for instance, DiscoveryCore’s module then imports back from marty_msf.framework.discovery, it closes the loop. In one real-world example, a project had code and data in __init__.py and submodules inter-depending; they noted it “doesn’t seem correct” and recommended refactoring so that __init__.py is bare and functionality moved into submodules[10].
Step-by-step to fix framework.discovery:
	•	Find self-references. Open framework/discovery/__init__.py and any discovery submodules. Look for import statements that reference the package itself. For example, search for import marty_msf.framework.discovery or any use of from . import X where X might re-import the package.
	•	Split into subpackages. The analysis suggests creating distinct modules, e.g.:
	•	framework/discovery/core.py for core discovery classes and functions.
	•	framework/discovery/impl.py or similar for implementation details.Then modify imports so that nothing in __init__.py causes a loop. For instance, instead of having classes defined in __init__.py, define them in core.py and have __init__.py do:
	•	# framework/discovery/__init__.py (after refactor)from .core import DiscoveryCore, DiscoveryManager__all__ = ["DiscoveryCore", "DiscoveryManager"]
	•	This keeps __init__.py minimal (just exporting symbols) and avoids running code during import[11][12].
	•	Adjust internal imports. Within submodules, use relative imports instead of importing from the package name. For example:
	•	# framework/discovery/manager.py# BEFORE (problematic):from marty_msf.framework.discovery import config# AFTER (safe):from . import config
	•	This ensures Python doesn’t reload the package’s __init__.py mid-import.
	•	Verify and test. After restructuring, try importing marty_msf.framework.discovery in a clean interpreter. There should be no ImportError about partial initialization. The analysis count should no longer list a self-cycle.
Case Study: framework.ml.feature_store
Similarly, marty_msf.framework.ml.feature_store shows itself in both its imports and imported-by lists[13]:
"marty_msf.framework.ml.feature_store": {    "imports": [        "marty_msf.framework.ml.feature_store"   // self-cycle    ],    "imported_by": [        "marty_msf.framework.ml.feature_store"   // self-cycle    ]}
This often happens when a package and a module share the same name. For example, if there is:
marty_msf/framework/ml/feature_store/__init__.pymarty_msf/framework/ml/feature_store/feature_store.py
and __init__.py does:
from .feature_store import SomeClass
but feature_store.py itself does an absolute import like from marty_msf.framework.ml.feature_store import ..., Python can get confused. In effect, the package feature_store is importing the module feature_store and vice versa.
How to fix feature_store:
	•	Rename or reorganize modules. Avoid having a module with the same name as the package. For example, rename feature_store.py to something like store_impl.py. Then:
	•	# framework/ml/feature_store/store_impl.pyclass FeatureStoreClient:    ...
	•	# framework/ml/feature_store/__init__.pyfrom .store_impl import FeatureStoreClient__all__ = ["FeatureStoreClient"]
	•	Now the package and module names differ, breaking the self-reference.
	•	Separate interface from implementation. Define a base or interface class in one module, and the concrete implementation in another. Then in __init__.py only expose the interface. For example:
	•	# interface.pyclass FeatureStoreInterface: ...# impl.pyfrom .interface import FeatureStoreInterfaceclass FeatureStore(FeatureStoreInterface): ...# __init__.pyfrom .interface import FeatureStoreInterfacefrom .impl import FeatureStore__all__ = ["FeatureStoreInterface", "FeatureStore"]
	•	This prevents a circular chain because code import paths are clear and one-way. The analysis suggested “Separate feature store interface from implementation” as the fix[8].
	•	Use explicit relative imports. Similar to above, ensure submodules import each other using from .submodule import X rather than importing from the package name. This confines Python’s import resolution within the package and avoids re-triggering __init__.py.
General Checklist: Identifying and Cleaning Heavy __init__.py Files
Even beyond these cases, any package’s __init__.py can become a source of cycles or import pain if it’s too “heavy”. Common signs include:
	•	Many imports or definitions in __init__.py. If you see dozens of lines of import statements or even class/function definitions, that’s a red flag. Python runs all of this code on import of the package.
	•	Side effects at import time. Any code that executes during import (e.g. building an object, configuring something, starting threads) is dangerous. For example, one project found that constructing a Flask app in __init__.py meant “you can not import without side effects… it’s easy to end up in hairy circular import issues”[14].
	•	Use of from . import X. A statement like from . import Submodule can recursively import the package again. If Submodule also refers back, a cycle forms.
	•	Errors mentioning partially initialized modules. These import errors are the most direct clue of a cycle. The traceback usually shows the same file(s) repeatedly.
To refactor safely:
	•	Move code out of __init__.py. Create submodules for functionality. For example, if your package had classes Foo and Bar in __init__.py, move them to foo.py and bar.py. Then in __init__.py just import or alias them:
	•	# BEFORE (heavy __init__.py)class Foo: ...class Bar: ...def helper(): ...# AFTER refactor:# foo.pyclass Foo: ...def helper(): ...# bar.pyclass Bar: ...# __init__.py (now minimal)from .foo import Foo, helperfrom .bar import Bar__all__ = ["Foo", "Bar", "helper"]
	•	This preserves the public API (users can still do from pkg import Foo) but removes logic from the import-time file.
	•	Avoid transitive imports in __init__.py. Don’t use from . import Query style in __init__.py, which implicitly re-imports the package. Instead, explicitly import from submodules. For example:
	•	# PROBLEM: re-imports packagefrom . import Query, Result# BETTER:from .elastic_query import Queryfrom .elastic_query_result import Result
	•	This change alone can break a self-cycle, as demonstrated in solving a similar issue[15][16].
	•	Enforce import rules. Use lint tools to prevent bad patterns. For instance, flake8-tidy-imports can forbid certain imports across a project[17]. You might ban imports from a package’s __init__.py within the package itself. This ensures internal modules use relative imports (from .helper import X) instead of from mypackage import X. (Notably, libraries like pandas follow this practice: code within pandas never does from pandas import ... internally.)
	•	Use __all__ for clarity. If you do export names from __init__.py, explicitly list them in __all__. This makes it clear what the public API is, and keeps import mechanisms predictable. It also prevents wildcard imports (from pkg import *) from pulling in unintended names.
Before/After Example
Suppose we have a package mypkg with a problematic import cycle:
# mypkg/__init__.py (BEFORE)from .moduleA import Afrom .moduleB import B# moduleA.pyfrom mypkg.moduleB import B   # Imports package and then moduleBclass A: ...# moduleB.pyfrom mypkg.moduleA import A   # Imports package and then moduleAclass B: ...
This can create a circular loop: importing mypkg triggers moduleA which tries to import mypkg again, etc.
Refactor:
# moduleA.py (after)from .moduleB import Bclass A: ...# moduleB.py (after)from .moduleA import Aclass B: ...
Or even better, invert one import or merge modules if tightly coupled.
Alternatively, if the cycle is due to __init__.py, you might do:
# __init__.py (before)-from .moduleA import A-from .moduleB import B# AFTER: keep it empty or only __all__ if needed__all__ = []
By moving exports to submodules and cleaning __init__.py, the cycle is broken.
Detecting and Preventing Cycles with Tools
Manual refactoring is essential, but automated tools can help catch or prevent these issues. For example, you can integrate a circular-import detector in your CI pipeline. One such tool is Pycycle. In a GitHub Actions workflow you might install and run:
pip install pycyclepycycle --format=json --fail-on-cycles src/
If any cycles are found, Pycycle exits with an error, causing the build to fail[18]. This ensures you catch new circular imports before code is merged.
Other useful tools and checks include:
	•	Static analysis linters: Run pylint, which has a “cyclic-import” warning. Use flake8 with plugins (e.g. flake8-tidy-imports) to forbid dangerous import patterns[17]. Recent tools like Ruff can enforce banned imports rules (derived from flake8-tidy-imports) efficiently.
	•	Import graph generators: Tools like snakefood or pydeps can visualize your import graph so you spot cycles by eye.
	•	Pre-commit hooks: Set up pre-commit checks to run these linters or Pycycle locally. This catches problems early.
	•	Monitored imports: Some teams even instrument a custom import hook to log import sequences (though this is advanced and not common).
	•	Type-checking workarounds: If cycles only exist for type hints, using typing.TYPE_CHECKING can defer imports (though true circular runtime imports must be fixed by refactoring).
The key is to treat your import graph as an architectural artifact. Automating checks (as demonstrated with Pycycle) helps prevent regressions[18][17]. Over time, disciplined patterns (like interface/implementation separation) and tooling will keep self-cycles from creeping back in.
References
	•	Python circular-import causes and effects[2][3].
	•	Case examples of heavy __init__.py causing import cycles[14][10].
	•	Suggested fixes (explicit imports, splitting modules)[15][12].
	•	Tools to detect/prevent cycles (pycycle CI example[18], flake8-tidy-imports[17]).

[1] [8] [12] ARCHITECTURE_ANALYSIS_REPORT.md
file://file_00000000c8e8622fa179704f0b670917
[2] [4] How to Fix a Circular Import in Python | Rollbar
https://rollbar.com/blog/how-to-fix-circular-import-in-python/
[3] [5] [6] [7] Closing The Loop On Python Circular Import Issue
https://www.mend.io/blog/closing-the-loop-on-python-circular-import-issue/
[9] [13] internal_import_analysis.json
file://file_00000000dbb461f58387ceaf44be6fcb
[10] [11] circular imports and busy __init__.py files · Issue #622 · mandiant/capa · GitHub
https://github.com/mandiant/capa/issues/622
[14] Don't build flask app in in __init__.py · Issue #7 · Open-EO/openeo-python-driver · GitHub
https://github.com/Open-EO/openeo-python-driver/issues/7
[15] [16] Python circular import in custom package and __init__.py - Stack Overflow
https://stackoverflow.com/questions/66694349/python-circular-import-in-custom-package-and-init-py
[17] python - Making functions available at `package/__init__.py`, how can I prevent module internal code from importing from the top level `__init__.py`? - Stack Overflow
https://stackoverflow.com/questions/71630256/making-functions-available-at-package-init-py-how-can-i-prevent-module-in
[18] Circular Imports in Python: The Architecture Killer That Breaks Production - DEV Community
https://dev.to/vivekjami/circular-imports-in-python-the-architecture-killer-that-breaks-production-539j
