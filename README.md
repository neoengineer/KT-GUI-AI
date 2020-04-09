# KT-GUI
### Experimental Jupyter Lab GUI for Ryze/DJI Tello EDU Drone


[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/neoengineer/final-project/master?urlpath=lab/tree/final-project.ipynb)


## How to Use this Template

### Work in Binder
- Launch a live notebook server with the notebook using [Binder](https://beta.mybinder.org/): [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/neoengineer/KT-GUI/master?urlpath=lab%2Ftree%2FTelloGUI-Video.ipynb)

### Work in Colab
- Launch an executable version of the notebook using [Google Colab](http://colab.research.google.com): [![Colab](https://colab.research.google.com/assets/colab-badge.svg)]
()

### Work locally (requires local installation of [git](https://git-scm.com/) and [JupyterLab](https://jupyterlab.readthedocs.io/en/stable/getting_started/installation.html))
- Clone the repo using a shell (below) or [GitHub Desktop](https://desktop.github.com)

```sh
git clone https://github.com/neoengineer/KT-GUI
jupyter lab
```

## Required packages

The packages used to run the code in the Binder instances are listed in [environment.yml](environment.yml) (Note that some of these exact version numbers may not be available on your platform: you may have to tweak them for your own use).


## Git version control
To use git in a Binder instance, you have to set up your username and email as below:

```sh
git config --global user.name "John Doe"
git config --global user.email johndoe@example.com
```

To avoid doing this every time you use Binder, include your username and email in the [git_setup.sh](git_setup.sh) file, which will be run via [postBuild](postBuild) immediately after building the Binder instance.


## License

The code in this repository is released under the [GPL V3 license](LICENSE).



Author: Thomas May
