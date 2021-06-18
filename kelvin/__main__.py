import os
import sys
from tap import Tap
from kelvin import lib

def maybe_extend_pythonpath(source_dir: str) -> None:
    """
    Looks for the presence of an _extensions directory inside
    the source website. If it's found, we'll import it.
    """
    extension_dir = os.path.join(source_dir, '_extensions')
    if os.path.exists(extension_dir):
        lib.logger.info("extending classpath")
        my_dir = os.path.dirname(__file__)
        sys.path.append(os.path.realpath(my_dir))
        sys.path.append(source_dir)
        import _extensions # type: ignore
    else:
        lib.logger.info("no extension dir exists %s" % extension_dir)


class Arguments(Tap):
    source_dir: str     # The source directory.
    dest_dir: str       # The directory to write the generated site.
    debug: bool = False # If true, prints out debugging information.

    def configure(self) -> None:
        self.add_argument('source_dir')
        self.add_argument('dest_dir')


def main() -> None:
    args = Arguments().parse_args()

    maybe_extend_pythonpath(args.source_dir)
    
    site = lib.Site(args.source_dir, args.dest_dir)
    site.transform()

if __name__ == "__main__":
    main()
