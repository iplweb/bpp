# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|

  config.vm.define "master", primary: true do |master|
      master.vm.box = "ubuntu/trusty64"
      master.vm.box_check_update = false

      # Ansible playbooks zarządzające serwisami - prosta sprawa:
      master.vm.synced_folder "../ANSIBLE-django-bpp/playbooks", 	"/home/vagrant/ansible-playbooks"

      # ... tak samo dla Ansible potrzebny jest katalog /etc/ansible z inwentarzem hostów:
      master.vm.synced_folder "../ANSIBLE-django-bpp/etc", 			"/etc/ansible", 					mount_options: ["dmode=777", "fmode=666"]

      # To jest potrzebne do budowania pakietów nginx, aby potem je móc podpisać i wrzucić
      # do PPA na launchpad
      master.vm.synced_folder "../ANSIBLE-django-bpp/.gnupg", 		"/home/vagrant/.gnupg", 			mount_options: ["dmode=700", "fmode=600"]

      # A to jest zamiast serwera devpi - tam budujemy pakiety Pythona i każdy host może tam coś od siebie wrzucić:
      master.vm.synced_folder "../wheelhouse", 	                    "/wheelhouse", 		mount_options: ["dmode=777", "fmode=666"]

      master.vm.network "private_network", ip: "192.168.111.100"

      master.vm.provision "shell", inline: <<-SHELL
        sudo apt-get update -qq
        sudo apt-get install -y git mercurial python-virtualenv build-essential mc emacs24-nox yaml-mode python-dev python3-dev sshpass

        wget https://bootstrap.pypa.io/get-pip.py

        sudo python get-pip.py
        sudo python3 get-pip.py

        git config --global user.email "michal.dtz@gmail.com"
        git config --global user.name "Michał Pasternak"
        git config --global core.autocrlf true

        # Ansible
        sudo pip2 install ansible

        # Hosts
        echo "192.168.111.101 staging" >> /etc/hosts

        echo "master" > /etc/hostname
        hostname `cat /etc/hostname`

        echo "alias jed=emacs24-nox" >> ~/.bash_profile

        # sshpass -p "vagrant" ssh -o StrictHostKeyChecking=no staging ls
      SHELL
  end

  config.vm.define "staging" do |staging|
      staging.vm.box = "ubuntu/trusty64"
      staging.vm.box_check_update = false

      staging.vm.synced_folder "../wheelhouse", "/home/vagrant/wheelhouse", mount_options: ["dmode=700", "fmode=600"]

      staging.vm.network "private_network", ip: "192.168.111.101"
      staging.vm.network "forwarded_port", guest: 80, host: 8080

      staging.vm.provision "shell", inline: <<-SHELL
        sudo apt-get update -qq
        sudo apt-get install -y sshpass

        # Hosts
        echo "192.168.111.100 master" >> /etc/hosts
        echo "staging" > /etc/hostname
        hostname `cat /etc/hostname`

        # sshpass -p "vagrant" ssh -o StrictHostKeyChecking=no master ls
      SHELL
  end

# master.vm.provider "virtualbox" do |vb|
#   # Display the VirtualBox GUI when booting the machine
#   vb.gui = true
#
#   # Customize the amount of memory on the VM:
#   vb.memory = "1024"
# end

# master.push.define "atlas" do |push|
#   push.app = "YOUR_ATLAS_USERNAME/YOUR_APPLICATION_NAME"
# end

end