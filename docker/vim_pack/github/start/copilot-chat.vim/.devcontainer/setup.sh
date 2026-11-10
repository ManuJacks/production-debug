cp .devcontainer/vimrc ~/.vimrc
vim +PluginInstall +qall

cp -r * ~/.vim/bundle/copilot-chat.vim/
cp .devcontainer/init.vim ~/.config/nvim/init.vim